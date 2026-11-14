class Solution:
    def topKFrequent(self, nums: List[int], k: int) -> List[int]:
        counts = []
        for x in set(nums):
            counts.append((nums.count(x), x))
        counts.sort(reverse=True)
        return [x for _, x in counts[:k]]
