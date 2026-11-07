class Solution:
    def wordBreak(self, s, wordDict):
        words = set(wordDict)

        def can_break(start):
            if start == len(s):
                return True
            for end in range(start + 1, len(s) + 1):
                if s[start:end] in words and can_break(end):
                    return True
            return False

        return can_break(0)
