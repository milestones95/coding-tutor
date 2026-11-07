class Solution:
    def subarraySum(self, nums, k):
        left = 0
        window_sum = 0
        count = 0
        for right in range(len(nums)):
            window_sum += nums[right]
            while window_sum > k and left <= right:
                window_sum -= nums[left]
                left += 1
            if window_sum == k:
                count += 1
        return count
