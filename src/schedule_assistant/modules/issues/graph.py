from collections import defaultdict
from typing import TypeVar

T = TypeVar("T")


class UndirectedGraph:
    def __init__(self, vertices_number: int = 0) -> None:
        self.create_graph(vertices_number)

    def create_graph(self, vertices_number: int) -> None:
        self.vertices_number = vertices_number
        self.graph = defaultdict(list)

    def add_edge(self, start: int, end: int) -> None:
        self.graph[start].append(end)
        self.graph[end].append(start)

    def dfs(self, start: int, used: list[bool], component: list[int]) -> None:
        used[start] = True
        component.append(start)
        for end in self.graph[start]:
            if used[end]:
                continue
            self.dfs(end, used, component)

    def get_connected_components(self) -> list[list[int]]:
        used = [False] * self.vertices_number
        result = []
        for vertex in range(self.vertices_number):
            if used[vertex]:
                continue
            component = []
            self.dfs(vertex, used, component)
            result.append(component)
        return result

    def get_multi_vertex_groups(
        self,
        elements: list[T],
        connected_components: list[list[int]],
    ) -> list[list[T]]:
        groups = []
        for component in connected_components:
            if len(component) == 1:
                continue
            group = []
            for i in component:
                group.append(elements[i])
            groups.append(group)
        return groups
