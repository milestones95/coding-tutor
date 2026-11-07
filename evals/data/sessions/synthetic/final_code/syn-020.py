class Solution:
    def removeStars(self, s: str) -> str:
        history = [""]
        for ch in s:
            if ch == "*":
                history.pop()
            else:
                history.append(history[-1] + ch)
        return history[-1]
