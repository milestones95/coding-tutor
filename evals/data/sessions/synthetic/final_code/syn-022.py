class Solution:
    def longestConsecutive(self, nums: list[int]) -> int:
        parent = {x: x for x in nums}

        def find(x):
            while parent[x] != x:
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for x in nums:
            if x + 1 in parent:
                union(x, x + 1)

        size = {}
        for x in parent:
            root = find(x)
            size[root] = size.get(root, 0) + 1
        return max(size.values(), default=0)
