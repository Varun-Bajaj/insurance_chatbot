from settings.setting import *
import networkx as nx

class NXGraphAlgorithm:
    def __init__(self):
        self.entities = TC_DETAILS
        self.nx_graph_info = GRAPH_INFO

    def get_relationship(self):
        relationships = []

        for table, fks in self.nx_graph_info.items():
            for fk in fks:
                d = {}
                d['from_model'] = table
                d['to_model'] = fk
                relationships.append(d)

        return relationships

    def build_graph(self):
        relationships = self.get_relationship()
        G = nx.DiGraph()
        # Add entity nodes
        for e in self.entities:
            G.add_node(e['Table_Name'], type="entity")
            # Add field nodes and edges
            for f in e['field']:
                G.add_node(f"{e['Table_Name']}.{f}", type="field")
                G.add_edge(e['Table_Name'], f"{e['Table_Name']}.{f}")
        # Add relationship edges
        for r in relationships:
            G.add_edge(r['from_model'], r['to_model'])
        return G

    def expand_path_graph(self, G, retrieve_entities, q):
        ans = []

        for i in range(len(retrieve_entities)):
            for j in range(0, len(retrieve_entities)):
                try:
                    if retrieve_entities[i] != retrieve_entities[j]:
                        path = nx.shortest_path(G, retrieve_entities[i], retrieve_entities[j])
                        ans.append(path)
                except nx.NetworkXNoPath:
                    continue

        q.put(ans)


class GraphAlgorithm:
    def __init__(self, final_source_tables, final_target_tables):
        self.ans = None
        self.source_tables = final_source_tables
        self.target_tables = [final_target_tables[0]]
        self.index = 0
        self.target_turn = True
        self.source_parent = {}
        self.target_parent = {}
        self.source_visited = {}
        self.target_visited = {}

        for table in self.source_tables:
            self.source_visited[table] = True
            self.source_parent[table] = None

        self.target_visited[self.target_tables[0]] = True
        self.target_parent[self.target_tables[0]] = None
        self.fk_dict = GRAPH_INFO

    def algorithm1(self):
        ## find the path using the all source_tables
        if self.target_tables in self.source_tables:
            self.ans = self.target_tables[0]

        else:
            while self.source_tables[self.index] in self.fk_dict.keys() and self.ans == None:
                source_table = self.source_tables[self.index]
                # source_visited[source_table] = True
                print(f"\nSource Table: {source_table}\n")

                if len(self.target_tables) > self.index:
                    target_table = self.target_tables[self.index]
                    # target_visited[target_table] = True
                    print(f"\nTarget table: {target_table}\n|")

                else:
                    target_table = self.target_tables[-1]

                source_fks = set(self.fk_dict[source_table])
                print(f"\nSource fks: {source_fks} and type {type(source_fks)}\n")

                if target_table in self.fk_dict.keys():
                    target_fks = set(self.fk_dict[target_table])

                else:
                    self.target_turn = False
                    target_fks = []

                print(f"\nTarget fks: {target_fks} and type {type(target_fks)}\n")

                # Push target tables foreign keys into the target tables list

                for t_fk in target_fks:
                    if t_fk in self.source_visited.keys() and t_fk in self.source_tables:
                        self.ans = t_fk
                        self.target_parent[t_fk] = target_table
                        break

                    else:
                        if t_fk not in self.source_visited.keys():
                            self.target_parent[t_fk] = target_table
                            self.target_visited[t_fk] = True
                            self.target_tables.append(t_fk)

                if self.ans is None:
                    for s_fk in source_fks:
                        if s_fk in self.target_visited.keys() and s_fk in self.target_tables:
                            self.ans = s_fk
                            self.source_parent[s_fk] = source_table
                            break

                        else:
                            if s_fk not in self.source_visited.keys():
                                self.source_parent[s_fk] = source_table
                                self.source_visited[s_fk] = True
                                self.source_tables.append(s_fk)

                self.index += 1

            print(self.source_tables)
            while self.target_turn and self.ans == None and self.target_tables[self.index] in self.fk_dict.keys() and \
                    self.source_tables[
                        self.index] not in self.fk_dict.keys():
                print("True")
                target_tabel = self.target_tables[self.index]
                self.target_visited[target_tabel] = True
                target_fks = self.fk_dict[target_tabel]

                for t_fk in target_fks:
                    if t_fk in self.source_tables:
                        self.ans = t_fk
                        self.target_visited[t_fk] = True
                        self.target_parent[t_fk] = target_tabel
                        break

                    else:
                        self.target_parent[t_fk] = target_tabel
                        self.target_visited[t_fk] = True
                        self.target_tables.append(t_fk)

                self.index += 1

        final_source_list = []
        final_target_list = []
        source_current = self.ans

        while self.source_parent[source_current] != None:
            final_source_list.append(source_current)
            source_current = self.source_parent[source_current]

        print(source_current)
        final_source_list.append(source_current)

        target_current = self.ans
        while self.target_parent[target_current] != None:
            final_target_list.append(target_current)
            target_current = self.target_parent[target_current]

        final_target_list.append(target_current)

        final_ans = []

        for i in range(len(final_source_list) - 1, 0, -1):
            final_ans.append(final_source_list[i])

        for table in final_target_list:
            final_ans.append(table)

        return [final_ans]

    def algorithm2(self):
        approach_2_ans = []

        for table in self.source_tables:
            temp_ans = None
            temp_source_tables = [table]
            temp_target_tables = self.target_tables
            temp_index = 0
            temp_target_turn = True
            temp_source_parent = {}
            temp_target_parent = {}
            temp_source_visited = {}
            temp_target_visited = {}
            temp_source_turn = True

            temp_source_visited[table] = True
            temp_source_parent[table] = None

            temp_target_visited[temp_target_tables[0]] = True
            temp_target_parent[temp_target_tables[0]] = None

            if temp_target_tables[0] == table:
                temp_target_turn = False
                temp_source_turn = False
                temp_ans = table

            while temp_source_turn and temp_source_tables[temp_index] in self.fk_dict.keys() and temp_ans == None:
                temp_source_table = temp_source_tables[temp_index]
                print(f"First come the temp source table: {temp_source_table}\n")
                if len(temp_target_tables) > temp_index:
                    temp_target_table = temp_target_tables[temp_index]

                else:
                    temp_target_table = temp_target_tables[-1]

                print(f"Temp target table: {temp_target_table}\n")

                temp_source_fks = set(self.fk_dict[temp_source_table])

                print(f"Temp source fks: {temp_source_fks}\n")

                if temp_target_table in self.fk_dict.keys():
                    temp_target_fks = set(self.fk_dict[temp_target_table])

                else:
                    temp_target_turn = False
                    temp_target_fks = []

                print(f"Temp Target fks: {temp_target_fks}\n")

                # Push target tables foreign keys into the target tables list

                for t_fk in temp_target_fks:
                    # print("Yes")
                    if t_fk in temp_source_visited.keys() and t_fk in temp_source_tables:
                        temp_ans = t_fk
                        temp_target_parent[t_fk] = temp_target_table
                        break

                    else:
                        if t_fk not in temp_source_visited.keys():
                            temp_target_parent[t_fk] = temp_target_table
                            temp_target_visited[t_fk] = True
                            temp_target_tables.append(t_fk)

                if temp_ans is None:
                    if len(temp_source_fks) == 0 and len(temp_source_tables) <= temp_index:
                        temp_source_turn = False
                        temp_index += 1
                        break;

                    else:
                        for s_fk in temp_source_fks:
                            if s_fk in temp_target_visited.keys() and s_fk in temp_target_tables:
                                print("YEs")
                                temp_source_turn = False
                                temp_ans = s_fk
                                print(f"Temp foriegn keys: {temp_ans}\n")
                                temp_source_parent[s_fk] = temp_source_table
                                break

                            else:
                                if s_fk not in temp_source_visited.keys():
                                    temp_source_parent[s_fk] = temp_source_table
                                    temp_source_visited[s_fk] = True
                                    temp_source_tables.append(s_fk)

                temp_index += 1

            while temp_target_turn and not temp_source_turn and temp_ans == None and temp_target_tables[
                temp_index] in self.fk_dict.keys() and temp_source_tables[temp_index] not in self.fk_dict.keys():
                print("True")
                temp_target_tabel = temp_target_tables[temp_index]
                temp_target_visited[temp_target_tabel] = True
                temp_target_fks = self.fk_dict[temp_target_tabel]

                for t_fk in temp_target_fks:
                    if t_fk in temp_source_tables:
                        temp_ans = t_fk
                        temp_target_visited[t_fk] = True
                        temp_target_parent[t_fk] = temp_target_tabel
                        break

                    else:
                        temp_target_parent[t_fk] = temp_target_tabel
                        temp_target_visited[t_fk] = True
                        temp_target_tables.append(t_fk)

                temp_index += 1

            print(temp_ans)

            temp_final_source_list = []
            temp_final_target_list = []
            temp_source_current = temp_ans

            while temp_source_parent[temp_source_current] != None:
                temp_final_source_list.append(temp_source_current)
                temp_source_current = temp_source_parent[temp_source_current]

            print(temp_source_current)
            temp_final_source_list.append(temp_source_current)

            temp_target_current = temp_ans
            while temp_target_parent[temp_target_current] != None:
                temp_final_target_list.append(temp_target_current)
                temp_target_current = temp_target_parent[temp_target_current]

            temp_final_target_list.append(temp_target_current)

            temp_final_ans = []

            for i in range(len(temp_final_source_list) - 1, 0, -1):
                temp_final_ans.append(temp_final_source_list[i])

            for table in temp_final_target_list:
                temp_final_ans.append(table)

            approach_2_ans.append(temp_final_ans)

            print("===============================================")
            print(f"\nFinal answer: {approach_2_ans}\n")
            print("================================================")

        return approach_2_ans
