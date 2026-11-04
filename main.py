
import hashlib
import shlex
import time
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# 1. 커밋 자료구조
# ============================================================

class Commit:
    """하나의 커밋이 가지는 정보를 저장한다."""

    def __init__(self, commit_hash, message, author, timestamp, parents, branch_name = "empty"):
        self.hash = commit_hash
        self.message = message
        self.author = author
        self.timestamp = timestamp
        
        # 부모 커밋이 여러 개일 수 있으므로 리스트로 관리한다.
        # 일반 커밋은 부모가 1개, 최초 커밋은 부모가 0개다.
        # Merge commit을 구현하면 부모가 2개가 될 수 있다.
        self.parents = parents

        self.branch_name = branch_name


# ============================================================
# 2. 직접 구현한 병합 정렬
# ============================================================

def merge_sort(items, key=lambda x: x):
    """
    Python의 sorted()와 list.sort()를 사용하지 않고
    병합 정렬(Merge Sort)을 구현한다.

    key 함수로 날짜, 작성자, 해시 등 비교 기준을 변경할 수 있다.
    평균 및 최악 시간복잡도: O(n log n)
    안정 정렬: 같은 값이면 왼쪽 항목을 먼저 선택하므로 안정적이다.
    """

    # 항목이 0개 또는 1개라면 이미 정렬된 상태다.
    if len(items) <= 1:
        return items[:]

    middle = len(items) // 2

    # 배열을 반으로 나누어 각각 정렬한다.
    left = merge_sort(items[:middle], key)
    right = merge_sort(items[middle:], key)

    result = []
    i = 0
    j = 0

    # 두 정렬된 배열을 비교하면서 하나로 합친다.
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    # 한쪽에 남은 항목을 결과에 추가한다.
    while i < len(left):
        result.append(left[i])
        i += 1

    while j < len(right):
        result.append(right[j])
        j += 1

    return result


# ============================================================
# 3. Mini Git
# ============================================================

class MiniGit:
    # 생성자
    def __init__(self):
        self.initialized = False
        self.current_author = None

        # 커밋 해시를 키로 사용하여 커밋을 빠르게 찾는다.
        # 평균적으로 해시맵 조회는 O(1)이다.
        self.commits = {}

        # 브랜치 이름(key) : 해당 브랜치의 최신 커밋 해시(value)
        self.branches = {}

        # 현재 체크아웃한 브랜치 이름
        # HEAD는 커밋이 아니라 브랜치를 가리킨다.
        self.head = None

        # 세션 내 커밋 해시의 중복을 방지하는 카운터
        self.commit_counter = 0

        # 역색인 1: 정규화한 키워드 -> 커밋 해시 집합
        self.keyword_index = {}

        # 역색인 2: 작성자 이름 -> 커밋 해시 집합
        self.author_index = {}

    def print_init(self):
        print("="*10, end="")
        print("print_init", end="")
        print("="*10)

        print(f"초기화 여부: {self.initialized}")
        print(f"작성자    : {self.current_author}")
        print(f"브랜치 목록: {self.branches}")
        print(f"현쟈 포인터: {self.head}")
        print(f"커밋 개수 : {self.commit_counter}")
        print(f"키워드 인덱스: {self.keyword_index}")
        print(f"작성자 인덱스: {self.author_index}")
        
        print("="*60)

    def print_branch(self):
        print("=" * 20, end="")
        print("print_branch", end="")
        print("=" * 20)

        for key, value in self.branches.items():
            print(f"branch [{key}] : commit hash [{value}]")
        
        print("="*60)


    def print_current_branch(self):
        print("="*10, end="")
        print("print_current_branch", end="")
        print("="*10)

        print(f"현재 브랜치: {self.head} : {self.branches[self.head]}")
        
        print("="*60)

    def print_log(self):
        print("="*10, end="")
        print("print_current_branch", end="")
        print("="*10)

        print(f"값 체크: self.head : {self.head}")

        commit_hash = self.branches[self.head]
        if commit_hash is None:
            return

        # print(commit_hash, type(commit_hash))
        current_commit = self.commits[commit_hash]
        print(current_commit)

        while current_commit is not None:
            print(current_commit.hash)
            print(current_commit.message)
            print(current_commit.author)
            print(current_commit.timestamp)
            print()
            print()
            current_commit = current_commit.parents

        
        print("="*60)
    # --------------------------------------------------------
    # 공통 검사 및 출력
    # --------------------------------------------------------

    def _require_initialized(self):
        """저장소 초기화 여부를 검사한다."""
        if not self.initialized:
            print("Repository not initialized")
            return False
        return True

    def _get_commit(self, commit_hash):
        """존재하는 커밋을 반환하고, 없으면 오류를 출력한다."""
        commit = self.commits.get(commit_hash)

        if commit is None:
            print(f"Unknown commit: {commit_hash}")

        return commit

    def _print_commit(self, commit):
        """커밋의 주요 정보를 출력한다."""

        dt = datetime.fromtimestamp(
            commit.timestamp,
            tz=ZoneInfo("Asia/Seoul")
        )

        # print(dt.strftime("%Y-%m-%d %H:%M:%S"))

        print(
            f"hash: {commit.hash} | "
            f"author: {commit.author} | "
            f"timestamp: {dt} | "
            f"message: {commit.message}"
        )

    # --------------------------------------------------------
    # INIT 명령어
    # --------------------------------------------------------

    def init(self, user_name):
        """저장소를 초기화하고 main 브랜치를 생성한다."""

        if not user_name:
            print("Invalid args")
            return

        # INIT을 다시 실행하면 새로운 저장소로 초기화한다.
        self.initialized = True
        self.current_author = user_name
        self.commits = {}
        self.branches = {"main": None}
        self.head = "main"
        self.commit_counter = 0
        self.keyword_index = {}
        self.author_index = {}

        print(f"Initialized repository.")
        print(f"Current branch: {self.head}")
        print(f"Current User: {user_name}")

    # --------------------------------------------------------
    # BRANCH
    # --------------------------------------------------------

    def branch(self, branch_name):
        """현재 커밋을 가리키는 새 브랜치를 생성한다."""

        if not self._require_initialized():
            return

        if not branch_name or branch_name in self.branches:
            print("Invalid args")
            return

        # 현재 브랜치가 가리키는 커밋을 새 브랜치도 가리킨다.
        current_commit = self.branches[self.head]
        self.branches[branch_name] = current_commit

        print(f"Created branch: {branch_name}")

    # --------------------------------------------------------
    # SWITCH
    # --------------------------------------------------------

    def switch(self, branch_name):
        """현재 HEAD가 가리키는 브랜치를 변경한다."""

        if not self._require_initialized():
            return

        if branch_name not in self.branches:
            print(f"Unknown branch: {branch_name}")
            return

        self.head = branch_name
        print(f"Switched to branch: {branch_name}")

    # --------------------------------------------------------
    # COMMIT
    # --------------------------------------------------------

    def commit(self, message):
        """새 커밋을 생성하고 브랜치와 역색인을 갱신한다."""

        if not self._require_initialized():
            return

        if not message:
            print("Invalid args")
            return

        # 현재 브랜치가 가리키는 커밋이 새 커밋의 부모다.
        parent_hash = self.branches[self.head]
        parents = [] if parent_hash is None else [parent_hash]

        timestamp = time.time()
        self.commit_counter += 1

        # 카운터를 해시 문자열에 포함하여 세션 내 고유성을 보장한다.
        # SHA-1은 실제 Git의 객체 해시를 그대로 구현한 것이 아니라
        # 이 Mini Git에서 식별자를 생성하기 위한 용도로 사용한다.
        raw_data = (
            f"{self.commit_counter}|{timestamp}|"
            f"{self.current_author}|{message}|{parents}"
        )
        digest = hashlib.sha1(raw_data.encode("utf-8")).hexdigest()[:12]
        commit_hash = f"c{self.commit_counter:06d}-{digest}"

        new_commit = Commit(
            commit_hash,
            message,
            self.current_author,
            timestamp,
            parents,
            self.head
        )

        # 1. 커밋 저장소에 추가한다.
        self.commits[commit_hash] = new_commit

        # 2. 현재 브랜치가 새 커밋을 가리키도록 이동한다.
        self.branches[self.head] = commit_hash

        # 3. 작성자 역색인을 갱신한다.
        self.author_index.setdefault(
            self.current_author, set()
        ).add(commit_hash)

        # 4. 메시지를 공백으로 분리하고 소문자로 정규화한다.
        #    예: "Add Login Feature" -> add, login, feature
        for keyword in message.lower().split():
            self.keyword_index.setdefault(
                keyword, set()
            ).add(commit_hash)

        print("Created commit:")
        self._print_commit(new_commit)
        print(f"[{self.head} {commit_hash}] {message}")
        

    # --------------------------------------------------------
    # LOG: 부모가 자식보다 먼저 출력되는 위상 정렬
    # --------------------------------------------------------

    def _topological_order(self):
        """
        Kahn 알고리즘으로 커밋 그래프를 위상 정렬한다.

        부모 -> 자식 방향으로 간선을 생각한다.
        부모가 없는 커밋부터 출력하므로 모든 부모가 자식보다 먼저
        출력된다. 이 순서는 최신순 정렬과는 다르다.
        """

        # 각 커밋의 부모 수를 계산한다.
        indegree = {
            commit_hash: len(commit.parents)
            for commit_hash, commit in self.commits.items()
        }

        # 부모 커밋 -> 자식 커밋 목록
        children = {
            commit_hash: []
            for commit_hash in self.commits
        }

        for commit_hash, commit in self.commits.items():
            for parent_hash in commit.parents:
                children[parent_hash].append(commit_hash)

        # 부모가 없는 커밋부터 처리한다.
        queue = [
            commit_hash
            for commit_hash, degree in indegree.items()
            if degree == 0
        ]

        result = []
        index = 0

        # pop(0) 대신 인덱스를 사용하여 불필요한 배열 이동을 피한다.
        while index < len(queue):
            current = queue[index]
            index += 1
            result.append(current)

            for child_hash in children[current]:
                indegree[child_hash] -= 1

                if indegree[child_hash] == 0:
                    queue.append(child_hash)

        # 정상적인 DAG라면 모든 커밋이 결과에 포함되어야 한다.
        if len(result) != len(self.commits):
            raise ValueError("Commit graph contains a cycle")

        return result

    def log(self, sort_by=None):
        """전체 커밋 로그를 출력한다."""

        if not self._require_initialized():
            return

        if sort_by not in (None, "date", "author"):
            print("Invalid args")
            return

        if sort_by is None:
            # 기본 LOG는 위상 정렬을 사용한다.
            hashes = self._topological_order()
            commits = [self.commits[h] for h in hashes]

        elif sort_by == "date":
            # 날짜 오름차순으로 정렬한다.
            commits = merge_sort(
                list(self.commits.values()),
                key=lambda commit: commit.timestamp
            )

        else:
            # 작성자 이름 오름차순으로 정렬한다.
            commits = merge_sort(
                list(self.commits.values()),
                key=lambda commit: commit.author.lower()
            )

        if not commits:
            print("No commits")
            return

        for commit in commits:
            self._print_commit(commit)

    # --------------------------------------------------------
    # PATH: 무방향 커밋 그래프의 최단 경로
    # --------------------------------------------------------
    # 보류
    def path(self, start_hash, end_hash):
        """
        부모 연결을 무방향 간선으로 취급하고 BFS로 최단 경로를 찾는다.

        이웃을 해시의 사전순으로 탐색하여 최단 경로가 여러 개일 때
        사전순으로 가장 작은 경로를 선택한다.
        """

        if not self._require_initialized():
            return

        if start_hash not in self.commits:
            print(f"Unknown commit: {start_hash}")
            return

        if end_hash not in self.commits:
            print(f"Unknown commit: {end_hash}")
            return

        # 시작과 도착이 같으면 경로는 해당 커밋 하나다.
        if start_hash == end_hash:
            print(start_hash)
            return

        # 부모 관계를 양방향 인접 리스트로 변환한다.
        graph = {h: [] for h in self.commits}

        for commit_hash, commit in self.commits.items():
            for parent_hash in commit.parents:
                graph[commit_hash].append(parent_hash)
                graph[parent_hash].append(commit_hash)

        # BFS에서 각 노드까지 도달하는 최단 경로를 저장한다.
        # 이웃을 사전순으로 탐색하므로 같은 길이의 경로 중
        # 사전순으로 가장 작은 경로가 먼저 발견된다.
        queue = [[start_hash]]
        visited = {start_hash}
        index = 0

        while index < len(queue):
            current_path = queue[index]
            index += 1
            current = current_path[-1]

            # 해시를 사전순으로 정렬한다.
            neighbors = merge_sort(graph[current])

            for neighbor in neighbors:
                if neighbor in visited:
                    continue

                next_path = current_path + [neighbor]

                if neighbor == end_hash:
                    print("->".join(next_path))
                    return

                visited.add(neighbor)
                queue.append(next_path)

        print("No path")

    # --------------------------------------------------------
    # ANCESTORS: 모든 조상 커밋 탐색
    # --------------------------------------------------------

    def ancestors(self, commit_hash):
        """
        지정한 커밋의 모든 조상을 중복 없이 출력한다.
        DFS vs BFS -> DFS가 좀 더 나아보임.
        """

        if not self._require_initialized():
            return

        if commit_hash not in self.commits:
            print(f"Unknown commit: {commit_hash}")
            return

        visited = set()
        stack = list(self.commits[commit_hash].parents)

        # 스택을 이용한 깊이 우선 탐색(DFS)
        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)

            # 부모가 여러 개인 커밋도 처리할 수 있다.
            stack.extend(self.commits[current].parents)

        if not visited:
            print("No ancestors")
            return

        # 출력 순서는 해시 사전순으로 정한다.
        # for ancestor_hash in merge_sort(list(visited)):
        #     self._print_commit(self.commits[ancestor_hash])

        for ancestor_hash in merge_sort(list(visited)):
            self._print_commit(self.commits[ancestor_hash])
                    
        

    # --------------------------------------------------------
    # SEARCH: 역색인을 이용한 검색
    # --------------------------------------------------------

    def search_keyword(self, keyword):
        """메시지 키워드 역색인으로 커밋을 검색한다."""

        if not self._require_initialized():
            return

        if not keyword:
            print("Invalid args")
            return

        # 메시지 토큰과 동일한 기준으로 소문자 정규화한다.
        tokens = keyword.lower().split()

        if not tokens:
            print("Invalid args")
            return

        # 여러 토큰이 입력되면 모든 토큰을 포함한 커밋을 찾는다.
        # 각 토큰의 인덱스 집합을 교집합으로 결합한다.
        result_hashes = None

        for token in tokens:
            matching = self.keyword_index.get(token, set())

            if result_hashes is None:
                result_hashes = set(matching)
            else:
                result_hashes &= matching

        self._print_search_results(result_hashes or set())

    def search_author(self, author):
        """작성자 역색인으로 커밋을 검색한다."""

        if not self._require_initialized():
            return

        if not author:
            print("Invalid args")
            return

        hashes = self.author_index.get(author, set())
        self._print_search_results(hashes)

    def _print_search_results(self, hashes):
        """검색 결과를 출력한다."""

        if not hashes:
            print("No commits found")
            return

        # 검색 결과는 날짜 오름차순으로 출력한다.
        commits = merge_sort(
            [self.commits[h] for h in hashes],
            key=lambda commit: commit.timestamp
        )

        for commit in commits:
            self._print_commit(commit)



def debug_init_info(git):
    git.print_init()
    pass

def debug_branch_info(git):
    git.print_branch()
    pass

def debug_current_branch_info(git):
    git.print_current_branch()
    pass

def debug_commit_log(git):
    git.print_log()

# ============================================================
# 4. CLI 명령어 파서 및 REPL
# ============================================================

def execute_command(git, line):
    """한 줄의 명령을 파싱하고 적절한 기능을 실행한다."""

    try:
        # 따옴표 안의 공백은 하나의 인자로 처리한다.
        # 예: COMMIT "Add login feature"
        args = shlex.split(line)
    except ValueError:
        print("Invalid args")
        return True


    # Todo: 삭제 예정
    print(args)

    # if not args:
    #     return True

    command = args[0].upper()
    values = args[1:]

    # INIT <user_name>
    if command == "INIT":
        if len(values) != 1:
            print("Invalid args")
        else:
            git.init(values[0])
    elif command == "DEBUG_INIT":
        debug_init_info(git)


    # BRANCH <branch_name>
    elif command == "BRANCH":
        if len(values) != 1:
            print("Invalid args")
        else:
            git.branch(values[0])

    elif command == "DEBUG_BRANCH":
        debug_branch_info(git)

    # SWITCH <branch_name>
    elif command == "SWITCH":
        if len(values) != 1:
            print("Invalid args")
        else:
            git.switch(values[0])
    elif command == "DEBUG_SWITCH":
        debug_current_branch_info(git)

    # COMMIT <message>
    elif command == "COMMIT":
        if len(values) != 1:
            print("Invalid args")
        else:
            git.commit(values[0])

    elif command == "DEBUG_COMMIT":
        debug_commit_log(git)

    # LOG
    # LOG --sort-by=date
    # LOG --sort-by=author
    elif command == "LOG":
        if len(values) == 0:
            git.log()
        elif len(values) == 1 and values[0].startswith("--sort-by="):
            option = values[0].split("=", 1)[1].lower()
            git.log(option)
        else:
            print("Invalid args")

    # PATH <commit1> <commit2>
    elif command == "PATH":
        if len(values) != 2:
            print("Invalid args")
        else:
            git.path(values[0], values[1])

    # ANCESTORS <commit_hash>
    elif command == "ANCESTORS":
        if len(values) != 1:
            print("Invalid args")
        else:
            git.ancestors(values[0])

    # SEARCH <keyword>
    # SEARCH --author=<name>
    elif command == "SEARCH":
        if len(values) == 1 and values[0].startswith("--author="):
            author = values[0].split("=", 1)[1]
            git.search_author(author)

        elif len(values) == 1:
            git.search_keyword(values[0])

        else:
            print("Invalid args")

    elif command in ("EXIT", "QUIT"):
        if values:
            print("Invalid args")
            return True
        print("Bye!")
        return False

    else:
        print(f"Unknown command: {args[0]}")

    return True


def main():
    """명령 입력과 실행을 반복하는 REPL."""

    git = MiniGit()

    print("Mini Git")
    print("Type HELP for available commands.")
    print("Type EXIT or QUIT to quit.")

    while True:
        try:
            line = input("mini-git> ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        # HELP는 저장소 초기화 전에도 사용할 수 있다.
        if line.strip().upper() == "HELP":
            print("INIT <user_name>")
            print("BRANCH <branch_name>")
            print("SWITCH <branch_name>")
            print('COMMIT "message"')
            print("LOG")
            print("LOG --sort-by=date")
            print("LOG --sort-by=author")
            print("PATH <commit1> <commit2>")
            print("ANCESTORS <commit_hash>")
            print("SEARCH <keyword>")
            print('SEARCH --author="author name"')
            print("EXIT / QUIT")
            continue

        if not execute_command(git, line):
            break


if __name__ == "__main__":
    main()
