class Solution:
    def findNumberOfLIS(self, nums: List[int]) -> int:
        best = 0
        for start in range(len(nums)):
            seq = [nums[start]]
            for x in nums[start + 1:]:
                if x > seq[-1]:
                    seq.append(x)
                elif len(seq) > 1 and seq[-2] < x < seq[-1]:
                    seq[-1] = x
            best = max(best, len(seq))
        return best
