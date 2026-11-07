class Solution:
    def minDistance(self, word1: str, word2: str) -> int:
        i = j = 0
        ops = 0
        while i < len(word1) and j < len(word2):
            if word1[i] == word2[j]:
                i += 1
                j += 1
            elif i + 1 < len(word1) and word1[i + 1] == word2[j]:
                ops += 1  # delete word1[i]
                i += 1
            elif j + 1 < len(word2) and word1[i] == word2[j + 1]:
                ops += 1  # insert word2[j]
                j += 1
            else:
                ops += 1  # replace
                i += 1
                j += 1
        ops += (len(word1) - i) + (len(word2) - j)
        return ops
