class Solution:
    def isPalindrome(self, s: str) -> bool:
        cleaned = "".join(ch.lower() for ch in s if ch.isalnum())

        def check(t):
            if len(t) <= 1:
                return True
            if t[0] != t[-1]:
                return False
            return check(t[1:-1])

        return check(cleaned)
