from ovos_config import Configuration
from ovos_plugin_manager.templates.pipeline import IntentPipelinePlugin, IntentMatch
from ovos_utils import classproperty
from ovos_utils.log import LOG

from padacioso import IntentContainer


def _munge(name, skill_id):
    return f"{name}:{skill_id}"


def _unmunge(munged):
    return munged.split(":", 2)


class PadaciosoPipelinePlugin(IntentPipelinePlugin):

    def __init__(self, bus, config=None):
        config = config or Configuration().get("padatious", {})  # deprecated
        super().__init__(bus, config)
        self.engines = {lang: IntentContainer(
            self.config.get("fuzz"), n_workers=self.workers)
            for lang in self.valid_languages}

    # plugin api
    @classproperty
    def matcher_id(self):
        return "padacioso"

    def match(self, utterances, lang, message):
        return self.calc_intent(utterances, lang=lang)

    def train(self):
        # no training step needed
        return True

    # implementation
    def _get_engine(self, lang=None):
        lang = lang or self.lang
        if lang not in self.engines:
            self.engines[lang] = IntentContainer(self.cache_dir)
        return self.engines[lang]

    def detach_intent(self, skill_id, intent_name):
        LOG.debug("Detaching padacioso intent: " + intent_name)
        with self.lock:
            munged = _munge(intent_name, skill_id)
            for lang in self.engines:
                self.engines[lang].remove_intent(munged)
        super().detach_intent(skill_id, intent_name)

    def detach_entity(self, skill_id, entity_name):
        LOG.debug("Detaching padacioso entity: " + entity_name)
        with self.lock:
            munged = _munge(entity_name, skill_id)
            for lang in self.engines:
                self.engines[lang].remove_entity(munged)
        super().detach_entity(skill_id, entity_name)

    def detach_skill(self, skill_id):
        LOG.debug("Detaching padacioso skill: " + skill_id)
        with self.lock:
            for lang in self.engines:
                for entity in (e for e in self.registered_entities if e.skill_id == skill_id):
                    munged = _munge(entity.name, skill_id)
                    self.engines[lang].remove_entity(munged)
                for intent in (e for e in self.registered_intents if e.skill_id == skill_id):
                    munged = _munge(intent.name, skill_id)
                    self.engines[lang].remove_intent(munged)
        super().detach_skill(skill_id)

    def register_entity(self, skill_id, entity_name, samples=None, lang=None):
        lang = lang or self.lang
        super().register_entity(skill_id, entity_name, samples, lang)
        container = self._get_engine(lang)
        samples = samples or [entity_name]
        with self.lock:
            container.add_entity(entity_name, samples)

    def register_intent(self, skill_id, intent_name, samples=None, lang=None):
        lang = lang or self.lang
        super().register_intent(skill_id, intent_name, samples, lang)
        container = self._get_engine(lang)
        samples = samples or [intent_name]
        intent_name = _munge(intent_name, skill_id)
        with self.lock:
            container.add_intent(intent_name, samples)

    def register_entity_from_file(self, skill_id, entity_name, file_name, lang=None):
        lang = lang or self.lang
        container = self._get_engine(lang)
        super().register_entity_from_file(skill_id, entity_name, file_name, lang)
        with self.lock:
            container.load_entity(entity_name, file_name)

    def register_intent_from_file(self, skill_id, intent_name, file_name, lang=None):
        lang = lang or self.lang
        container = self._get_engine(lang)
        super().register_intent_from_file(skill_id, intent_name, file_name, lang)
        intent_name = _munge(intent_name, skill_id)
        with self.lock:
            container.load_intent(intent_name, file_name)

    def calc_intent(self, utterance, min_conf=0.0, lang=None):
        lang = lang or self.lang
        container = self._get_engine(lang)
        min_conf = min_conf or self.config.get("min_conf", 0.35)
        utterance = utterance.strip().lower()
        with self.lock:
            intent = container.calc_intent(utterance).__dict__
        if intent["conf"] < min_conf:
            return None

        if isinstance(intent["utterance"], list):
            intent["utterance"] = " ".join(intent["utterance"])

        intent_type, skill_id = _unmunge(intent["intent_type"])
        return IntentMatch(intent_service=self.matcher_id,
                           intent_type=intent_type,
                           intent_data=intent.pop("entities"),
                           confidence=intent["conf"],
                           utterance=utterance,
                           skill_id=skill_id)
