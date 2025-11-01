from collections import defaultdict, deque
from typing import Any, Tuple, Dict, List, Set, Union

"""
generate graph representation of the poset based on a dictionary
""" 
def generate_graph(dic : Dict[Union[str, Tuple[str, ...]], Any]) -> Dict[Tuple[str, ...], List[Tuple[str, ...]]]:
    hasse_diagram : Dict[Tuple[str, ...], List[Tuple[str, ...]]] = defaultdict(list)
    ranks         : Dict[int,             List[Set[str]]]        = defaultdict(list) 

    if dic:
        for key in dic.keys():
            key_set = set(key) if isinstance(key, tuple) else {key}
            rank = len(key_set)
            ranks[rank].append(key_set)

        for rank in sorted(ranks.keys()):
            current_keys = ranks[rank]
            for current_key in current_keys:
                hasse_diagram[tuple(current_key)] = []
                for shorter_rank in range(rank):
                    if shorter_rank in ranks:
                        for subset_key in ranks[shorter_rank]:
                            if subset_key < current_key:
                                hasse_diagram[tuple(current_key)].append(tuple(subset_key))
                
    return dict(simplify_graph(hasse_diagram))

"""
Filters out non-maximal subsets from a given dictionary of subset relations
"""
def simplify_graph(hasse_diagram : Dict[Tuple[str, ...], List[Tuple[str, ...]]]) -> Dict[Tuple[str, ...], List[Tuple[str, ...]]]:
    maximal_subsets = defaultdict(list)

    for key in hasse_diagram:
        current_subsets = hasse_diagram[key]
        current_set = set(map(tuple, current_subsets)) 
        filtered_subsets = [subset for subset in current_subsets
                            if not any(set(subset) < set(other) for other in current_set)]
        maximal_subsets[key] = filtered_subsets

    return maximal_subsets

"""
return maximal elements of graph
"""  
def maximal_elements(graph : Dict[Tuple[str, ...], List[Tuple[str, ...]]]) -> Set[Tuple[str, ...]]:
    vertices = set(graph.keys())
    vertices_with_incoming_edge = set(neighbor for neighbors in graph.values() for neighbor in neighbors)
    return vertices - vertices_with_incoming_edge

"""
selects handler from graph providing most coverage of the element
"""      
def max_element(graph : Dict[Tuple[str, ...], List[Tuple[str, ...]]], element : Tuple[str, ...]) -> Set[Union[str, Tuple[str, ...]]]:
    res     : Set[Tuple[str, ...]] = set()
    seen    : Set[Tuple[str, ...]] = set()
    res_set : Set[str]             = set()
    max_of_graph = maximal_elements(graph)
    print(f"max_element({max_of_graph})=", end='')
    list_max = deque(max_of_graph)
    # print('list', list_max)
    while not len(list_max) == 0:
        p = list_max.pop()
        tuple_p = p if isinstance(p, tuple) else (p,)
        set_p = set(tuple_p)
        if p in seen:
            continue
        seen.add(p)
        if set_p <= set(element) and not set_p <= res_set:
            res.add(p)
            res_set |= set_p
        elif len(set_p & set(element)) > 0:
            for neigh in graph.get(p, []):
                list_max.append(neigh)
    final_res : Set[str | Tuple[str, ...]] = {elem[0] if len(elem) == 1 else elem for elem in res}
    print(final_res)
    return final_res
