class TreeFragment:
    """(Abstract) empty sentence fragment"""

    def __init__(self, tree):
        """
        Construct a sentence tree fragment which is merely a wrapper for
        a list of Strings

        Args:
            tree (?): Base tree for the sentence fragment, type depends on
                        subclass, refer to those subclasses
        """
        self._tree = tree

    def tree(self):
        """Return the represented sentence tree as raw data."""
        return self._tree

    def expand(self):
        """
        Expanded version of the fragment. In this case an empty sentence.

        Returns:
            List<List<str>>: A list with an empty sentence (= token/string list)
        """
        return [[]]

    def __str__(self):
        return self._tree.__str__()

    def __repr__(self):
        return self._tree.__repr__()


class Word(TreeFragment):
    """
    Single word in the sentence tree.

    Construct with a string as argument.
    """

    def expand(self):
        """
        Creates one sentence that contains exactly that word.

        Returns:
            List<List<str>>: A list with the given string as sentence
                                (= token/string list)
        """
        return [[self._tree]]


class Sentence(TreeFragment):
    """
    A Sentence made of several concatenations/words.

    Construct with a List<TreeFragment> as argument.
    """

    def expand(self):
        """
        Creates a combination of all sub-sentences.

        Returns:
            List<List<str>>: A list with all subsentence expansions combined in
                                every possible way
        """
        old_expanded = [[]]
        for sub in self._tree:
            sub_expanded = sub.expand()
            new_expanded = []
            while len(old_expanded) > 0:
                sentence = old_expanded.pop()
                for new in sub_expanded:
                    new_expanded.append(sentence + new)
            old_expanded = new_expanded
        return old_expanded


class SentenceTree(TreeFragment):
    """
    A Combination of possible sub-sentences.

    Construct with List<TreeFragment> as argument.
    """

    def expand(self):
        """
        Returns all of its options as seperated sub-sentences.

        Returns:
            List<List<str>>: A list containing the sentences created by all
                                expansions of its sub-sentences
        """
        options = []
        for option in self._tree:
            options.extend(option.expand())
        return options


class SentenceTreeParser:
    """
    Generate sentence token trees from a list of sentence
    ['1', '(', '2', '|', '3, ')'] -> [['1', '2'], ['1', '3']]
    """

    def __init__(self, sentence):
        # the syntax for .optionally is square brackets
        # "hello [world]"
        # this is equivalent to using .one_of
        # "hello (world|)
        sentence = sentence.replace("[", "(").replace("]", "|)")
        self.sentence = sentence

    def _parse(self):
        """
        Generate sentence token trees
        ['1', '(', '2', '|', '3, ')'] -> ['1', ['2', '3']]
        """
        self._current_position = 0
        return self._parse_expr()

    def _parse_expr(self):
        """
        Generate sentence token trees from the current position to
        the next closing parentheses / end of the list and return it
        ['1', '(', '2', '|', '3, ')'] -> ['1', [['2'], ['3']]]
        ['2', '|', '3'] -> [['2'], ['3']]
        """
        # List of all generated sentences
        sentence_list = []
        # Currently active sentence
        cur_sentence = []
        sentence_list.append(Sentence(cur_sentence))
        # Determine which form the current expression has
        while self._current_position < len(self.sentence):
            cur = self.sentence[self._current_position]
            self._current_position += 1
            if cur == '(':
                # Parse the subexpression
                subexpr = self._parse_expr()
                # Check if the subexpression only has one branch
                # -> If so, append "(" and ")" and add it as is
                normal_brackets = False
                if len(subexpr.tree()) == 1:
                    normal_brackets = True
                    cur_sentence.append(Word('('))
                # add it to the sentence
                cur_sentence.append(subexpr)
                if normal_brackets:
                    cur_sentence.append(Word(')'))
            elif cur == '|':
                # Begin parsing a new sentence
                cur_sentence = []
                sentence_list.append(Sentence(cur_sentence))
            elif cur == ')':
                # End parsing the current subexpression
                break
            # TODO anything special about {sth}?
            else:
                cur_sentence.append(Word(cur))
        return SentenceTree(sentence_list)

    def expand_parentheses(self):
        tree = self._parse()
        return tree.expand()


def expand_parentheses(sent):
    """
    ['1', '(', '2', '|', '3, ')'] -> [['1', '2'], ['1', '3']]
    For example:
    Will it (rain|pour) (today|tomorrow|)?
    ---->
    Will it rain today?
    Will it rain tomorrow?
    Will it rain?
    Will it pour today?
    Will it pour tomorrow?
    Will it pour?
    Args:
        sent (list<str>): List of sentence in sentence
    Returns:
        list<list<str>>: Multiple possible sentences from original
    """
    expanded = SentenceTreeParser(sent).expand_parentheses()
    return ["".join(_).strip() for _ in expanded]


def clean_braces(example: str) -> str:
    """
    Normalizes {{entity}} to {entity}
    @param example: utterance example to clean
    @return: cleaned example
    """
    clean = example.replace('{{', '{').replace('}}', '}')
    return clean


def translate_padatious(example: str) -> str:
    """
    Translate Padatious `:0` syntax to standard regex
    @param example: input intent example
    @return: parsed intent example with Padatious syntax replaced with regex
    """
    if ':0' not in example:
        return example
    tokens = example.split()
    i = 0
    for idx, token in enumerate(tokens):
        if token == ":0":
            tokens[idx] = '{' + f'word{i}:word' + '}'
            i += 1
    return " ".join(tokens)


def normalize_example(example: str) -> str:
    return clean_braces(translate_padatious(example))
