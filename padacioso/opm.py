"""Intent service wrapping padacioso."""

from functools import lru_cache
from os.path import isfile
from typing import Optional, Dict, List, Union

from langcodes import closest_match
from ovos_bus_client.client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager, Session
from ovos_config.config import Configuration
from ovos_plugin_manager.templates.pipeline import ConfidenceMatcherPipeline, IntentHandlerMatch
from ovos_utils import flatten_list
from ovos_utils.fakebus import FakeBus
from ovos_utils.lang import standardize_lang_tag
from ovos_utils.log import LOG, log_deprecation

from padacioso import IntentContainer as FallbackIntentContainer
from padacioso.domain_engine import DomainIntentContainer


class PadaciosoIntent:
    """
    A set of data describing how a query fits into an intent
    Attributes:
        name (str): Name of matched intent
        sent (str): The input utterance associated with the intent
        conf (float): Confidence (from 0.0 to 1.0)
        matches (dict of str -> str): Key is the name of the entity and
            value is the extracted part of the sentence
    """

    def __init__(self, name, sent, matches=None, conf=0.0):
        self.name = name
        self.sent = sent
        self.matches = matches or {}
        self.conf = conf

    def __getitem__(self, item):
        return self.matches.__getitem__(item)

    def __contains__(self, item):
        return self.matches.__contains__(item)

    def get(self, key, default=None):
        return self.matches.get(key, default)

    def __repr__(self):
        return repr(self.__dict__)


class PadaciosoPipeline(ConfidenceMatcherPipeline):
    """Service class for padacioso intent matching."""

    def __init__(self, bus: Optional[Union[MessageBusClient, FakeBus]] = None,
                 config: Optional[Dict] = None):
        super().__init__(config=config or {}, bus=bus)

        core_config = Configuration()
        self.lang = standardize_lang_tag(core_config.get("lang", "en-US"))
        langs = core_config.get('secondary_langs') or []
        if self.lang not in langs:
            langs.append(self.lang)
        langs = [standardize_lang_tag(lang) for lang in langs]
        self.conf_high = self.config.get("conf_high") or 0.95
        self.conf_med = self.config.get("conf_med") or 0.8
        self.conf_low = self.config.get("conf_low") or 0.5
        self.workers = self.config.get("workers") or 4

        self.containers = {lang: self._build_container() for lang in langs}

        self.bus.on('padatious:register_intent', self.register_intent)
        self.bus.on('padatious:register_entity', self.register_entity)
        self.bus.on('detach_intent', self.handle_detach_intent)
        self.bus.on('detach_skill', self.handle_detach_skill)

        self.registered_intents = []
        self.registered_entities = []
        self.max_words = 50  # if an utterance contains more words than this, don't attempt to match
        LOG.debug('Loaded Padacioso intent parser.')

    @property
    def padacioso_config(self) -> Dict:
        log_deprecation("self.padacioso_config is deprecated, access self.config directly instead", "1.0.0")
        return self.config

    @padacioso_config.setter
    def padacioso_config(self, val):
        log_deprecation("self.padacioso_config is deprecated, access self.config directly instead", "1.0.0")
        self.config = val

    def _match_level(self, utterances, limit, lang=None,
                     message: Optional[Message] = None) -> Optional[IntentHandlerMatch]:
        """Match intent and make sure a certain level of confidence is reached.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
            limit (float): required confidence level.
        """
        LOG.debug(f'Padacioso Matching confidence > {limit}')
        # call flatten in case someone is sending the old style list of tuples
        utterances = flatten_list(utterances)
        lang = standardize_lang_tag(lang or self.lang)
        padacioso_intent = self.calc_intent(utterances, lang, message)
        if padacioso_intent is not None and padacioso_intent.conf > limit:
            skill_id = padacioso_intent.name.split(':')[0]
            return IntentHandlerMatch(match_type=padacioso_intent.name,
                               match_data=padacioso_intent.matches,
                               skill_id=skill_id,
                               utterance=padacioso_intent.sent)

    def match_high(self, utterances: List[str], lang: str, message: Message) -> Optional[IntentHandlerMatch]:
        """Intent matcher for high confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, self.conf_high, lang, message)

    def match_medium(self, utterances: List[str], lang: str, message: Message) -> Optional[IntentHandlerMatch]:
        """Intent matcher for medium confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, self.conf_med, lang, message)

    def match_low(self, utterances: List[str], lang: str, message: Message) -> Optional[IntentHandlerMatch]:
        """Intent matcher for low confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, self.conf_low, lang, message)

    # ------------------------------------------------------------------
    # Container-shape hooks - overridden by DomainPadaciosoPipeline
    # ------------------------------------------------------------------

    def _build_container(self):
        """Build a per-language intent container.

        Subclasses can override to swap the container type (e.g. for the
        hierarchical :class:`DomainIntentContainer`).
        """
        return FallbackIntentContainer(self.config.get("fuzz"),
                                       n_workers=self.workers)

    def _container_add_intent(self, container, name: str, samples: List[str]) -> None:
        """Add an intent to a single-language container."""
        container.add_intent(name, samples)

    def _container_add_entity(self, container, name: str, samples: List[str]) -> None:
        """Add an entity to a single-language container."""
        container.add_entity(name, samples)

    def _container_remove_intent(self, container, name: str) -> None:
        """Remove an intent from a single-language container."""
        container.remove_intent(name)

    def _container_remove_entity(self, container, name: str) -> None:
        """Remove an entity from a single-language container."""
        container.remove_entity(name)

    def _container_has_intent(self, container, name: str) -> bool:
        """Return whether the container already knows ``name`` (reload path)."""
        return name in getattr(container, "intent_samples", {})

    # ------------------------------------------------------------------

    def __detach_intent(self, intent_name):
        """ Remove an intent if it has been registered.

        Args:
            intent_name (str): intent identifier
        """
        if intent_name in self.registered_intents:
            self.registered_intents.remove(intent_name)
            for lang in self.containers:
                self._container_remove_intent(self.containers[lang], intent_name)

    def handle_detach_intent(self, message):
        """Messagebus handler for detaching padacioso intent.

        Args:
            message (Message): message triggering action
        """
        self.__detach_intent(message.data.get('intent_name'))

    def __detach_entity(self, name, lang):
        """ Remove an entity.

        Args:
            entity name
            entity lang
        """
        if lang in self.containers:
            self._container_remove_entity(self.containers[lang], name)

    def handle_detach_skill(self, message):
        """Messagebus handler for detaching all intents for skill.

        Args:
            message (Message): message triggering action
        """
        skill_id = message.data['skill_id']
        remove_list = [i for i in self.registered_intents if skill_id in i]
        for i in remove_list:
            self.__detach_intent(i)
        skill_id_colon = skill_id + ":"
        for en in self.registered_entities:
            if en["name"].startswith(skill_id_colon):
                self.__detach_entity(en["name"], en["lang"])

    def _register_object(self, message, object_name, register_func):
        """Generic method for registering a padacioso object.

        Args:
            message (Message): trigger for action
            object_name (str): type of entry to register
            register_func (callable): function to call for registration
        """
        file_name = message.data.get('file_name')
        samples = message.data.get("samples")
        name = message.data['name']

        LOG.debug('Registering Padacioso ' + object_name + ': ' + name)

        if (not file_name or not isfile(file_name)) and not samples:
            LOG.error('Could not find file ' + file_name)
            return

        if not samples and isfile(file_name):
            with open(file_name) as f:
                samples = [line.strip() for line in f.readlines()]

        register_func(name, samples)

    def register_intent(self, message):
        """Messagebus handler for registering intents.

        Args:
            message (Message): message triggering action
        """
        lang = message.data.get('lang', self.lang)
        lang = standardize_lang_tag(lang)
        if lang in self.containers:
            self.registered_intents.append(message.data['name'])
            try:
                self._register_object(
                    message, 'intent',
                    lambda n, s: self._container_add_intent(self.containers[lang], n, s),
                )
            except RuntimeError:
                name = message.data.get('name', "")
                # padacioso fails on reloading a skill, just ignore
                if not self._container_has_intent(self.containers[lang], name):
                    raise

    def register_entity(self, message):
        """Messagebus handler for registering entities.

        Args:
            message (Message): message triggering action
        """
        lang = message.data.get('lang', self.lang)
        lang = standardize_lang_tag(lang)
        if lang in self.containers:
            self.registered_entities.append(message.data)
            self._register_object(
                message, 'entity',
                lambda n, s: self._container_add_entity(self.containers[lang], n, s),
            )

    def calc_intent(self, utterances: List[str], lang: str = None,
                    message: Optional[Message] = None) -> Optional[PadaciosoIntent]:
        """
        Get the best intent match for the given list of utterances. Utilizes a
        thread pool for overall faster execution. Note that this method is NOT
        compatible with Padacioso, but is compatible with Padacioso.
        @param utterances: list of string utterances to get an intent for
        @param lang: language of utterances
        @return:
        """
        if isinstance(utterances, str):
            utterances = [utterances]  # backwards compat when arg was a single string
        utterances = [u for u in utterances if len(u.split()) < self.max_words]
        if not utterances:
            LOG.error(f"utterance exceeds max size of {self.max_words} words, skipping padacioso match")
            return None

        lang = lang or self.lang

        lang = self._get_closest_lang(lang)
        if lang is None:  # no intents registered for this lang
            return None

        sess = SessionManager.get(message)

        intent_container = self.containers.get(lang)
        intents = [self._calc_one(utt, intent_container, sess)
                   for utt in utterances]
        intents = [i for i in intents if i is not None]
        # select best
        if intents:
            return max(intents, key=lambda k: k.conf)

    def _calc_one(self, utt: str, intent_container, sess: Session) -> Optional[PadaciosoIntent]:
        """Single-utterance matcher hook.

        The flat pipeline scans a single :class:`IntentContainer`.
        Subclasses can override to add domain routing.
        """
        return _calc_padacioso_intent(utt, intent_container, sess)

    def _get_closest_lang(self, lang: str) -> Optional[str]:
        if self.containers:
            lang = standardize_lang_tag(lang)
            closest, score = closest_match(lang, list(self.containers.keys()))
            # https://langcodes-hickford.readthedocs.io/en/sphinx/index.html#distance-values
            # 0 -> These codes represent the same language, possibly after filling in values and normalizing.
            # 1- 3 -> These codes indicate a minor regional difference.
            # 4 - 10 -> These codes indicate a significant but unproblematic regional difference.
            if score < 10:
                return closest
        return None

    def shutdown(self):
        self.bus.remove('padatious:register_intent', self.register_intent)
        self.bus.remove('padatious:register_entity', self.register_entity)
        self.bus.remove('detach_intent', self.handle_detach_intent)
        self.bus.remove('detach_skill', self.handle_detach_skill)


@lru_cache(maxsize=128)  # covers burst of multiple ASR hypotheses without thrashing
def _calc_padacioso_intent(utt: str,
                           intent_container: FallbackIntentContainer,
                           sess: Session) -> \
        Optional[PadaciosoIntent]:
    """
    Try to match an utterance to an intent in an intent_container
    @param args: tuple of (utterance, IntentContainer)
    @return: matched PadaciosoIntent
    """
    try:
        intents = [i for i in intent_container.calc_intents(utt)
                   if i is not None
                   and i["name"] not in sess.blacklisted_intents
                   and i["name"].split(":")[0] not in sess.blacklisted_skills]
        if len(intents) == 0:
            return None
        best_conf = max(x.get("conf", 0) for x in intents if x.get("name"))
        ties = [i for i in intents if i.get("conf", 0) == best_conf]
        if not ties:
            return None
        # TODO - how to disambiguate ?
        intent = ties[0]
        intent.pop("_matched_regex", None)
        if "entities" in intent:
            intent["matches"] = intent.pop("entities")
        intent["sent"] = utt
        intent = PadaciosoIntent(**intent)
        intent.sent = utt
        return intent
    except Exception as e:
        LOG.error(e)


class DomainPadaciosoPipeline(PadaciosoPipeline):
    """Hierarchical, two-level padacioso pipeline.

    Same behaviour as :class:`PadaciosoPipeline` except the underlying
    per-language container is a :class:`DomainIntentContainer`. Each
    registered intent is routed to a domain == ``skill_id`` (taken from
    the intent label's ``<skill_id>:<intent>`` prefix); inference first
    picks the most likely domain via the top-level classifier and then
    resolves the intent inside that domain.

    Configuration is read from ``intents.ovos_padacioso_domain_pipeline``
    so this pipeline can coexist with the flat plugin in the same OVOS
    instance. Accepts every key the flat plugin does.

    Example ``mycroft.conf``::

        "intents": {
            "ovos-padacioso-domain-pipeline": {
                "fuzz": true
            }
        }
    """

    def __init__(self, bus: Optional[Union[MessageBusClient, FakeBus]] = None,
                 config: Optional[Dict] = None):
        if config is None:
            config = (
                Configuration().get("intents", {})
                .get("ovos_padacioso_domain_pipeline") or {}
            )
        super().__init__(bus=bus, config=config)

    # ------------------------------------------------------------------
    # Overrides - swap the container and route adds/removes through domains
    # ------------------------------------------------------------------

    @staticmethod
    def _domain_of(name: str) -> str:
        """Extract the domain (skill_id) from a ``skill_id:intent`` label."""
        return name.split(":", 1)[0] if ":" in name else name

    def _build_container(self):
        return DomainIntentContainer(fuzz=bool(self.config.get("fuzz")),
                                     n_workers=self.workers)

    def _container_add_intent(self, container: DomainIntentContainer,
                              name: str, samples: List[str]) -> None:
        domain = self._domain_of(name)
        container.register_domain_intent(domain, name, samples)

    def _container_add_entity(self, container: DomainIntentContainer,
                              name: str, samples: List[str]) -> None:
        # Entities are shared across domains: add to every existing
        # sub-container so templates resolve uniformly.
        for sub in container.domains.values():
            sub.add_entity(name, samples)

    def _container_remove_intent(self, container: DomainIntentContainer,
                                  name: str) -> None:
        domain = self._domain_of(name)
        container.remove_domain_intent(domain, name)
        # If the domain has no remaining intents, drop the domain entry.
        sub = container.domains.get(domain)
        if sub is not None and not getattr(sub, "intent_samples", {}):
            container.remove_domain(domain)

    def _container_remove_entity(self, container: DomainIntentContainer,
                                  name: str) -> None:
        for sub in container.domains.values():
            try:
                sub.remove_entity(name)
            except Exception:
                pass

    def _container_has_intent(self, container: DomainIntentContainer,
                              name: str) -> bool:
        domain = self._domain_of(name)
        sub = container.domains.get(domain)
        if sub is None:
            return False
        return name in getattr(sub, "intent_samples", {})

    # ------------------------------------------------------------------
    # Matching - delegate to DomainIntentContainer.calc_intent
    # ------------------------------------------------------------------

    def _calc_one(self, utt: str, intent_container: DomainIntentContainer,
                  sess: Session) -> Optional[PadaciosoIntent]:
        try:
            match = intent_container.calc_intent(utt)
            if not match or not match.get("name"):
                return None
            label = match["name"]
            if label in sess.blacklisted_intents:
                return None
            if label.split(":")[0] in sess.blacklisted_skills:
                return None
            match.pop("_matched_regex", None)
            if "entities" in match:
                match["matches"] = match.pop("entities")
            match["sent"] = utt
            intent = PadaciosoIntent(**match)
            intent.sent = utt
            return intent
        except Exception as e:
            LOG.error(e)
            return None
