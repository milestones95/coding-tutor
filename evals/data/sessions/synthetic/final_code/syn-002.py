class Solution:
    def searchRange(self, nums: list[int], target: int) -> list[int]:
        if not nums:
            return [-1, -1]
        if nums[0] == nums[-1]:
            return [0, len(nums) - 1]

        def lower_bound(x):
            lo, hi = 0, len(nums)
            while lo < hi:
                mid = (lo + hi) // 2
                if nums[mid] < x:
                    lo = mid + 1
                else:
                    hi = mid
            return lo

        first = lower_bound(target)
        if first == len(nums) or nums[first] != target:
            return [-1, -1]
        last = lower_bound(target + 1) - 1
        return [first, last]
