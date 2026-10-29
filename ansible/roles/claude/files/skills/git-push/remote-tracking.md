# upstream が [gone]・upstream と違う remote・追跡 ref の残り

SKILL.md の Step 1 の 2. で次のどれかになったときに読む。

- 表の行が「末尾が `[gone]`」か「upstream と違う remote」に決まった
- 「追跡 ref の残りの確認」で、`rev-parse` が exit 0 で `ls-remote` が exit 2 だった

force push を頼まれたときは、下の「末尾が [gone] の行」と「upstream と違う remote の行」の数え方と確認を、force-push.md の「Step 1 の 3.」を当ててから使う（push 先から消えるコミットがあれば、足すコミットが 0 件でも終えない）。

## 目次

- 追跡 ref の残りを見つけたとき
- 末尾が [gone] の行
- upstream と違う remote の行
- 3. の fetch の要否（残りがある remote）

## 追跡 ref の残りを見つけたとき

`rev-parse` が exit 0 で `ls-remote` が exit 2（push 先にブランチが無い）なら、その追跡 ref はリモートで消されたブランチの残りである。fetch しても `fetch.prune` が無効（git の既定）ならその ref は消えず、通常の push はここまで fetch もしないので、`for-each-ref` は `[gone]` を出さない（`[ahead 1]` などが付くか、差が無ければ何も付かない）。`git branch -vv` なども gone を出さない。
upstream がその ref なら、upstream を `[gone]` として表を引き直す。1 行目のまま push すると、リモートで消されたブランチを確認なしで作り直す（`* [new branch]` で exit 0）。`[gone]` の行の 0 件の理由は、`[gone]` を `リモートで消された（追跡 ref は残っている）` に替えて書く。

`[gone]` として引いた行と upstream と違う remote の行では、下の 2 つの節の `--not --remotes=<remote>` で数えるところを `git log --oneline HEAD --not --exclude=<remote>/<branch> --remotes=<remote>` にする。残りを除かないと、その ref にあるコミットが数えられず、push 先に無いのに 0 件で終わる。`--exclude` の値に `refs/remotes/` を付けると何も除かない。
初回 push の行では（force push で残りが分かったときも）除かない。除くと、`-u` を付けずに push してマージされたブランチが 1 件以上になり、確認なしで作り直す。

残りを `[gone]` として引いたとき、fetch していなければほかの追跡 ref もマージより前のままなので、merge commit でマージしたブランチのコミットも数え、`[gone]` の行の 0 件では終わらずに作り直すかを聞く（どれも Git 2.54.0 で実測）。確認には、マージ済みのコミットも並びうることを添える。数えすぎても確認か中止に倒れるだけなので、これを避けるための fetch はしない。

## 末尾が [gone] の行

upstream のリモートブランチが消えた行で、remote の名指しが無いか upstream の remote のとき。

聞く前に、3. のコミットを `git log --oneline HEAD --not --remotes=<upstream の remote>` で数える（`@{upstream}` は解決できず exit 128 になる）。
0 件なら聞かずに 3. の 0 件として終え、理由に `[gone]` を添える（`— push しない（push するコミットが無いため。upstream の origin/feature/x は [gone]）`）。merge commit でマージされたブランチはここで終わる。
1 件以上なら `AskUserQuestion` で確認する。PR がマージ済みでブランチが消された可能性があり（squash でマージされたブランチは 1 件以上残る）、push するとマージ済みのブランチを作り直す（git-pr のルール 11「マージした直後にベースを最新へ戻す」を見る）。
push すると答えたら `git push <upstream の remote> <branch>` に決まる。upstream の設定は残っており、push で追跡が戻るので `-u` は要らない（どれも Git 2.54.0 で実測）。

## upstream と違う remote の行

upstream が同名のリモートブランチ（末尾が `[gone]` のものを含む）で、名指しの remote が upstream の remote と違うとき。

聞く前に、3. のコミットを `git log --oneline HEAD --not --remotes=<名指しの remote>` で数える。`@{upstream}..HEAD` は upstream の remote との差で、upstream の remote に push 済みなら 0 件になって push せずに終わる（Git 2.54.0 で実測）。`[gone]` では上の「末尾が [gone] の行」のとおり使えない。
0 件なら聞かずに 3. の 0 件として終える。
1 件以上なら `AskUserQuestion` で確認する。`-u` で upstream を名指しの remote へ付け替えるかが決まらない（付け替えずに push すると upstream は変わらない）。答えで `git push -u <名指しの remote> <branch>` か `git push <名指しの remote> <branch>` に決まる。

## 3. の fetch の要否（残りがある remote）

SKILL.md の 3. で `git for-each-ref --count=1 refs/remotes/<remote>/` が空かを見るとき、残りがあると分かった remote では `--exclude=refs/remotes/<remote>/<branch>` を足して見る。fetch せずに push しただけの remote は残りだけで空にならず、数える側で残りを除くと push 済みのコミットまで並ぶ。`for-each-ref` の `--exclude` は `log` と逆で、`refs/remotes/` から書かないと何も除かない（どれも Git 2.54.0 で実測）。
