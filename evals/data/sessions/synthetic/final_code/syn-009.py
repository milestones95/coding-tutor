class Solution:
    def merge(self, intervals):
        intervals.sort(key=lambda iv: iv[0])
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = end
            else:
                merged.append([start, end])
        return merged
