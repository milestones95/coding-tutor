class Solution:
    def canFinish(self, numCourses, prerequisites):
        graph = [[] for _ in range(numCourses)]
        for course, pre in prerequisites:
            graph[course].append(pre)

        on_path = set()

        def has_cycle(node):
            if node in on_path:
                return True
            on_path.add(node)
            for nxt in graph[node]:
                if has_cycle(nxt):
                    return True
            on_path.remove(node)
            return False

        for c in range(numCourses):
            if has_cycle(c):
                return False
        return True
