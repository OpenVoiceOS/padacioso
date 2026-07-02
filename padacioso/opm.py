"""Intent service wrapping padacioso."""

from functools import lru_cache
from os.path import isfile
from typing import Optional, Dict, List, Union

from ovos_bus_client.client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_bus_client.session import SessionManager, Session
from ovos_config.config import Configuration
from ovos_plugin_manager.templates.pipeline import ConfidenceMatcherPipeline, IntentHandlerMatch
from ovos_spec_tools import closest_lang, standardize_lang, SpecMessage
from ovos_utils import flatten_list
from ovos_utils.fakebus import FakeBus
from ovos_utils.log import LOG, log_deprecation

from padacioso import IntentContainer as FallbackIntentContainer


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
        self.lang = standardize_lang(core_config.get("lang", "en-US"))
        langs = core_config.get('secondary_langs') or []
        if self.lang not in langs:
            langs.append(self.lang)
        langs = [standardize_lang(lang) for lang in langs]
        self.conf_high = self.config.get("conf_high") or 0.95
        self.conf_med = self.config.get("conf_med") or 0.8
        self.conf_low = self.config.get("conf_low") or 0.5
        self.workers = self.config.get("workers") or 4

        self.containers = {lang: FallbackIntentContainer(
            self.config.get("fuzz"), n_workers=self.workers)
            for lang in langs}

        # legacy padatious registration topics (back-compat)
        self.bus.on('padatious:register_intent', self.register_intent)
        self.bus.on('padatious:register_entity', self.register_entity)
        self.bus.on('detach_intent', self.handle_detach_intent)
        self.bus.on('detach_skill', self.handle_detach_skill)

        # OVOS-INTENT-4 registration topics. padacioso is a TEMPLATE engine,
        # so it consumes the template registration topic (§6) and ignores
        # ovos.intent.register.keyword (§11 conformance). Entity (§7) and
        # deregister/enable/disable (§8) are consumed too.
        self.bus.on(SpecMessage.INTENT_REGISTER_TEMPLATE.value, self.handle_register_template)
        self.bus.on(SpecMessage.ENTITY_REGISTER.value, self.handle_register_entity)
        self.bus.on(SpecMessage.INTENT_DEREGISTER.value, self.handle_deregister_intent)
        self.bus.on(SpecMessage.ENTITY_DEREGISTER.value, self.handle_deregister_entity)
        self.bus.on(SpecMessage.SKILL_DEREGISTER.value, self.handle_deregister_skill)
        self.bus.on(SpecMessage.INTENT_ENABLE.value, self.handle_enable_intent)
        self.bus.on(SpecMessage.INTENT_DISABLE.value, self.handle_disable_intent)

        self.registered_intents = []
        self.registered_entities = []
        # OVOS-INTENT-4 §8.5 enable/disable: keep the expanded template samples
        # keyed by (lang, internal_name) so a disabled intent can be re-armed
        # without losing its definition. Populated by the spec template path.
        self._template_samples = {}
        # A disable can target an intent registered via *either* the spec
        # template path or the legacy ``padatious:register_intent`` path (which
        # does not fill ``_template_samples``). Stash the live samples pulled
        # from the container at disable time, keyed by (lang, internal_name), so
        # enable can re-arm regardless of how the intent was registered.
        self._disabled_intents = {}
        self.max_words = 50  # if an utterance contains more words than this, don't attempt to match
        LOG.debug('Loaded Padacioso intent parser.')

    @staticmethod
    def _internal_name(skill_id: str, intent_name: str) -> str:
        """Compose the engine-internal namespaced intent name.

        padacioso stores intents under ``<skill_id>:<intent_name>`` (the
        match result's skill_id is derived by splitting on ``:``). OVOS-INTENT-4
        carries ``skill_id`` and ``intent_name`` as distinct fields (§3.2), so
        recompose the legacy form here.
        """
        if intent_name and skill_id and not intent_name.startswith(f"{skill_id}:"):
            return f"{skill_id}:{intent_name}"
        return intent_name or skill_id

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
        lang = standardize_lang(lang or self.lang)
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

    def __detach_intent(self, intent_name):
        """ Remove an intent if it has been registered.

        Args:
            intent_name (str): intent identifier
        """
        if intent_name in self.registered_intents:
            self.registered_intents.remove(intent_name)
            for lang in self.containers:
                self.containers[lang].remove_intent(intent_name)
            # the container was mutated; drop stale cached matches
            _calc_padacioso_intent.cache_clear()

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
            self.containers[lang].remove_entity(name)
            # the container was mutated; drop stale cached matches
            _calc_padacioso_intent.cache_clear()

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
        # the container was mutated; drop stale cached matches
        _calc_padacioso_intent.cache_clear()

    def register_intent(self, message):
        """Messagebus handler for registering intents.

        Args:
            message (Message): message triggering action
        """
        lang = message.data.get('lang', self.lang)
        lang = standardize_lang(lang)
        if lang in self.containers:
            self.registered_intents.append(message.data['name'])
            try:
                self._register_object(message, 'intent',
                                      self.containers[lang].add_intent)
            except RuntimeError:
                name = message.data.get('name', "")
                # padacioso fails on reloading a skill, just ignore
                if name not in self.containers[lang].intent_samples:
                    raise

    def register_entity(self, message):
        """Messagebus handler for registering entities.

        Args:
            message (Message): message triggering action
        """
        lang = message.data.get('lang', self.lang)
        lang = standardize_lang(lang)
        if lang in self.containers:
            self.registered_entities.append(message.data)
            self._register_object(message, 'entity',
                                  self.containers[lang].add_entity)

    # ------------------------------------------------------------------
    # OVOS-INTENT-4 bus handlers (consumed alongside the legacy topics)
    # ------------------------------------------------------------------
    def _warn_malformed(self, topic: str, data: Dict, reason: str):
        """§5.3 / §6.3 / §7.2 — log a malformed registration at WARN.

        fire-and-forget means this log is the producer's only debugging signal.
        """
        LOG.warning(
            f"rejecting malformed registration on {topic}: "
            f"skill_id={data.get('skill_id')!r} "
            f"intent_name={data.get('intent_name') or data.get('entity_name')!r} "
            f"lang={data.get('lang')!r} reason={reason}")

    def handle_register_template(self, message: Message):
        """OVOS-INTENT-4 §6 — register a template intent.

        Maps the spec payload (``skill_id`` + ``intent_name`` + ``samples`` +
        optional ``blacklist`` + ``lang``) onto the engine's namespaced
        ``add_intent`` call, reusing the legacy registration internals.
        """
        topic = SpecMessage.INTENT_REGISTER_TEMPLATE.value
        data = message.data
        skill_id = data.get("skill_id")
        intent_name = data.get("intent_name")
        samples = data.get("samples")
        if not samples:  # §6.3 malformed
            self._warn_malformed(topic, data, "missing or empty 'samples'")
            return
        if not intent_name or not skill_id:  # §3.2 identity required
            self._warn_malformed(topic, data, "missing 'skill_id' or 'intent_name'")
            return

        lang = standardize_lang(data.get("lang", self.lang))
        if lang not in self.containers:
            LOG.debug(f"ignoring template registration for unconfigured lang: {lang}")
            return

        name = self._internal_name(skill_id, intent_name)
        # §8.1 replacement is implicit: a re-registration replaces the prior entry
        self.__detach_intent(name)
        self.registered_intents.append(name)
        self._template_samples[(lang, name)] = list(samples)
        try:
            self.containers[lang].add_intent(name, samples)
        except RuntimeError:
            if name not in self.containers[lang].intent_samples:
                raise

        blacklist = data.get("blacklist")
        if blacklist:  # §6.1 suppression phrases
            self.containers[lang].exclude_keywords(name, list(blacklist))

    def handle_register_entity(self, message: Message):
        """OVOS-INTENT-4 §7 — register an entity value-set hint."""
        topic = SpecMessage.ENTITY_REGISTER.value
        data = message.data
        skill_id = data.get("skill_id")
        entity_name = data.get("entity_name")
        samples = data.get("samples")
        if not samples:  # §7.2 malformed
            self._warn_malformed(topic, data, "missing or empty 'samples'")
            return
        if not entity_name or not skill_id:
            self._warn_malformed(topic, data, "missing 'skill_id' or 'entity_name'")
            return

        lang = standardize_lang(data.get("lang", self.lang))
        if lang not in self.containers:
            LOG.debug(f"ignoring entity registration for unconfigured lang: {lang}")
            return

        name = self._internal_name(skill_id, entity_name)
        # §8.1 replacement is implicit
        self.__detach_entity(name, lang)
        self.registered_entities = [
            e for e in self.registered_entities
            if not (e.get("name") == name and e.get("lang") == lang)]
        self.registered_entities.append({"name": name, "lang": lang})
        self.containers[lang].add_entity(name, samples)

    def _intent_langs(self, message: Message) -> List[str]:
        """Resolve which container langs a deregister/enable/disable targets.

        §8.2 — when ``lang`` is omitted every registered language is affected.
        """
        lang = message.data.get("lang")
        if lang:
            lang = standardize_lang(lang)
            return [lang] if lang in self.containers else []
        return list(self.containers.keys())

    def handle_deregister_intent(self, message: Message):
        """OVOS-INTENT-4 §8.2 — remove one intent (all langs if lang omitted)."""
        skill_id = message.data.get("skill_id")
        intent_name = message.data.get("intent_name")
        name = self._internal_name(skill_id, intent_name)
        self.__detach_intent(name)
        for lang in self._intent_langs(message):
            self._template_samples.pop((lang, name), None)

    def handle_deregister_entity(self, message: Message):
        """OVOS-INTENT-4 §8.3 — remove one entity (all langs if lang omitted)."""
        skill_id = message.data.get("skill_id")
        entity_name = message.data.get("entity_name")
        name = self._internal_name(skill_id, entity_name)
        for lang in self._intent_langs(message):
            self.__detach_entity(name, lang)
        self.registered_entities = [
            e for e in self.registered_entities if e.get("name") != name]

    def handle_deregister_skill(self, message: Message):
        """OVOS-INTENT-4 §8.4 — remove everything owned by a skill_id."""
        skill_id = message.data.get("skill_id")
        if not skill_id:
            return
        prefix = skill_id + ":"
        for i in [i for i in self.registered_intents
                  if i == skill_id or i.startswith(prefix)]:
            self.__detach_intent(i)
            for lang in self.containers:
                self._template_samples.pop((lang, i), None)
        for en in list(self.registered_entities):
            if en["name"] == skill_id or en["name"].startswith(prefix):
                self.__detach_entity(en["name"], en["lang"])
        self.registered_entities = [
            e for e in self.registered_entities
            if not (e["name"] == skill_id or e["name"].startswith(prefix))]

    def handle_disable_intent(self, message: Message):
        """OVOS-INTENT-4 §8.5 — suppress an intent without losing its definition.

        The container has no native disable, so the regexes are removed from
        matching while the expanded samples are retained for re-arming (§8.5).
        """
        skill_id = message.data.get("skill_id")
        intent_name = message.data.get("intent_name")
        name = self._internal_name(skill_id, intent_name)
        for lang in self._intent_langs(message):
            samples = self.containers[lang].intent_samples.get(name)
            if samples is not None:
                # retain the live samples so a legacy-registered intent (which
                # never populated ``_template_samples``) can still be re-armed
                self._disabled_intents[(lang, name)] = list(samples)
                self.containers[lang].remove_intent(name)

    def handle_enable_intent(self, message: Message):
        """OVOS-INTENT-4 §8.5 — re-arm a previously disabled intent."""
        skill_id = message.data.get("skill_id")
        intent_name = message.data.get("intent_name")
        name = self._internal_name(skill_id, intent_name)
        for lang in self._intent_langs(message):
            if name in self.containers[lang].intent_samples:
                self._disabled_intents.pop((lang, name), None)
                continue  # already enabled, no-op
            # prefer the samples stashed at disable time (works for both the
            # spec and legacy registration paths); fall back to the retained
            # template definition for a spec-registered intent.
            samples = (self._disabled_intents.pop((lang, name), None)
                       or self._template_samples.get((lang, name)))
            if samples:
                self.containers[lang].add_intent(name, samples)

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
        # Session is not hashable, so it cannot be an lru_cache key. Pass the
        # blacklists it carries as frozensets (hashable) instead.
        blacklisted_intents = frozenset(sess.blacklisted_intents or [])
        blacklisted_skills = frozenset(sess.blacklisted_skills or [])

        intent_container = self.containers.get(lang)
        # Invalidate the burst cache once per match call: registrations,
        # deregistrations, disables and detaches all mutate the container
        # between calls, and a stale cache entry would keep a removed intent
        # matching. The intra-call burst (multiple ASR hypotheses below) still
        # benefits from the cache after this clear.
        _calc_padacioso_intent.cache_clear()
        intents = [_calc_padacioso_intent(utt, intent_container,
                                          blacklisted_intents, blacklisted_skills)
                   for utt in utterances]
        intents = [i for i in intents if i is not None]
        # select best
        if intents:
            return max(intents, key=lambda k: k.conf)

    def _get_closest_lang(self, lang: str) -> Optional[str]:
        if self.containers:
            return closest_lang(lang, list(self.containers.keys()))
        return None

    def shutdown(self):
        self.bus.remove('padatious:register_intent', self.register_intent)
        self.bus.remove('padatious:register_entity', self.register_entity)
        self.bus.remove('detach_intent', self.handle_detach_intent)
        self.bus.remove('detach_skill', self.handle_detach_skill)
        self.bus.remove(SpecMessage.INTENT_REGISTER_TEMPLATE.value, self.handle_register_template)
        self.bus.remove(SpecMessage.ENTITY_REGISTER.value, self.handle_register_entity)
        self.bus.remove(SpecMessage.INTENT_DEREGISTER.value, self.handle_deregister_intent)
        self.bus.remove(SpecMessage.ENTITY_DEREGISTER.value, self.handle_deregister_entity)
        self.bus.remove(SpecMessage.SKILL_DEREGISTER.value, self.handle_deregister_skill)
        self.bus.remove(SpecMessage.INTENT_ENABLE.value, self.handle_enable_intent)
        self.bus.remove(SpecMessage.INTENT_DISABLE.value, self.handle_disable_intent)


@lru_cache(maxsize=128)  # covers burst of multiple ASR hypotheses without thrashing
def _calc_padacioso_intent(utt: str,
                           intent_container: FallbackIntentContainer,
                           blacklisted_intents: frozenset = frozenset(),
                           blacklisted_skills: frozenset = frozenset()) -> \
        Optional[PadaciosoIntent]:
    """
    Try to match an utterance to an intent in an intent_container

    The session blacklists are passed as hashable frozensets so this stays
    ``lru_cache``-able (Session is unhashable under ovos-bus-client>=2.4.0a1).
    @return: matched PadaciosoIntent
    """
    try:
        intents = [i for i in intent_container.calc_intents(utt)
                   if i is not None
                   and i["name"] not in blacklisted_intents
                   and i["name"].split(":")[0] not in blacklisted_skills]
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
