class Solution:
    def dailyTemperatures(self, temperatures):
        n = len(temperatures)
        answer = [0] * n
        stack = []  # indices still waiting for a warmer day
        for i, t in enumerate(temperatures):

            still_waiting = []
            for j in stack:
                if temperatures[j] < t:
                    answer[j] = i - j
                else:
                    still_waiting.append(j)
            still_waiting.append(i)
            stack = still_waiting
        return answer
