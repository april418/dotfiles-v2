# dotfiles-v2

## Installation

```sh
bash -c "$(curl -L g.oftn.lv/dtfls)"
```

## Codex / ChatGPT のグローバル指示

`codex` ロールは `~/.codex/AGENTS.md` にグローバル指示を配置する。
`CODEX_HOME` が設定されていれば、そのディレクトリに配置する。
次の原本を連結し、Codex 向けの環境差の説明を添えて生成する。

- `ansible/roles/claude/files/AGENTS.md`
- `ansible/roles/claude/files/rules/*.md`（ファイル名順）
- `ansible/roles/claude/files/characters/<選択した名前>.md`

原本は分割したまま管理できる。生成したファイルには規則の本文が入るため、
Codex が参照先を開くかどうかに依存しない。rules の削除やキャラクターの変更も再生成時に反映する。
既存の配置先を更新するときは Ansible がバックアップを残す。

Codex CLI と Codex / ChatGPT デスクトップの、新しいチャットから適用される。
グローバル指示を読むための追加プラグインは不要。
Claude Code の権限設定は Codex には適用されない。hook は、下のとおり同じロールで Codex にも渡す。
skill など、収録していない Claude 側のファイルは、存在して利用できる場合だけ参照する。

`dotfiles character set <名前>` は Claude Code のキャラクターを配置した後、
Codex のグローバル指示も再生成する。`none` を選ぶと両方でキャラクターを使わない。
この処理では Codex CLI や Node.js をインストールしない。

同じロールで Codex CLI（`@openai/codex`）も固定バージョンでインストールする。
配置先は `~/.local/share/codex`（`XDG_DATA_HOME` があればその下）で、
`~/.local/bin/codex` から起動する。ChatGPT アプリ同梱版とは別に管理する。
Node.js が無い、または古い場合はインストールをスキップして知らせるので、
nvm で対応する Node.js を入れてから流し直す。

同じロールで、Claude Code のプラグインと同じ yomiyasu の skill を Codex にも置く（[Claude Code のプラグイン](#claude-code-のプラグイン)）。
`claude_yomiyasu_version` のタグを `~/.local/share/yomiyasu`（`XDG_DATA_HOME` があればその下）に浅く clone し、
Codex がユーザー全体の skill を探す `~/.agents/skills/yomiyasu` を、その中の `skills/yomiyasu` へのリンクにする。
置き場は `CODEX_HOME` を設定していても変わらない。ChatGPT アプリ同梱の codex も同じ場所を読むので、
Codex CLI を入れられなかったときも置く。skill の名前は Codex でも `yomiyasu:yomiyasu` になる
（skill のフォルダにある `.codex-plugin/plugin.json` による）。Codex は skill の変化を自分で拾い、
一覧に出てこなければ Codex を起動し直す。一覧に載ったかは、モデルを呼ばずに数えられる。
1 なら載っていて、0 なら載っていない。グローバル指示にも `yomiyasu:yomiyasu` の文字があるので、一覧の行の形で数える。

```sh
codex debug prompt-input | grep -c -F -e '- yomiyasu:yomiyasu: '
```

同じロールで、Claude Code に配る skill のうち `codex_shared_skills`（`ansible/roles/codex/vars/main.yml`）に挙げたものを
Codex にも見せる。`~/.agents/skills/<名前>` を、`claude` ロールが置いた `~/.claude/skills/<名前>` へのリンクにするので、
プレイブックを流すたびに Claude Code と同じ版になる。frontend-design は `claude` ロールがプラグインで入れ、
`~/.claude/skills` には無いので、`claude_frontend_design_skill_url` の SKILL.md を
`~/.local/share/dotfiles/codex-skills/frontend-design/`（`XDG_DATA_HOME` があればその下）に取り、そこへリンクする
（`codex_shared_skill_sources`）。Claude Code の subagent と worktree の分離を前提にした `orchestrate` は入れていない。
skill の中の `AskUserQuestion` などの名前は、グローバル指示の冒頭にあるとおり Codex が読み替える。
Claude Code の skill を足したり改名したり消したりしたら、Codex に見せるかを決めて `codex_shared_skills` も直す。
`claude` ロールは古い `~/.claude/skills/<旧名>` を消さず、一覧から外しても `~/.agents/skills` のリンクは残るので、
どちらも `evacuate` で退避する。古いコピーが残っていると、知らせずにそれへリンクする。

`~/.agents/skills` の yomiyasu と `codex_shared_skills` の名前に、リンクではないフォルダ（`npx skills add -g` で入れたものや、
下の取り込みが写したものなど）があれば、置き換えずに知らせる。`evacuate` で退避してから流し直す。
別の場所へのリンクと壊れたリンクは、流すたびに張り替える。リンク元の無い skill は、置かずに知らせる。

同じロールで、Claude Code の hook のうち `codex_shared_hooks`（`ansible/roles/codex/vars/main.yml`）に挙げたものを
`~/.codex/hooks.json`（`CODEX_HOME` があればその下）に登録する。登録は `ansible/roles/claude/files/settings.json` の `hooks` から作り、
コマンドは `claude` ロールが置いた `~/.claude/hooks/` のスクリプトをそのまま指すので、スクリプトの更新は Codex にも届く。
Codex のシェルのツールは hook に `Bash` という名前で渡るので、matcher も Claude Code と同じものが当たる。
`reply-language-guard.py` は Claude Code の会話記録の形を読むので入れていない。hook を足したり改名したりしたら、
Codex に登録するかを決めて `codex_shared_hooks` も直す。一覧の名前が `settings.json` の hook に無ければ、登録せずに知らせる。
Codex は信頼した hook だけを走らせる。信頼はスクリプトの中身ではなく、`hooks.json` の中の位置（イベントと、その中の組と hook の順番）と、
matcher・コマンド・`statusMessage`・`timeout` といった登録の内容で覚える。登録が変わった hook は Codex で信頼し直すまで走らず、
共有する hook を既存のものより前に足すと、後ろの hook も位置がずれて信頼し直しになる。`hooks.json` を書き換えたときは
プレイブックが知らせる。`hooks.json` はこのロールが書くので、Codex で足した hook は流すたびに消える（前の内容は Ansible のバックアップに残る）。
Codex は hook の additionalContext が 2,500 トークン（4 バイトを 1 トークンと数える）を超えると、先頭と末尾だけを残して
ファイルへ退避し、そのパスを載せる。`reload-claude-md.sh` が本文を省く上限は Claude Code に合わせた 9,000 文字なので、
日本語でおよそ 3,300 文字を超える状態ファイルは、Codex では途中が省かれる。

Codex / ChatGPT デスクトップの Settings → Import にある Claude Code からの取り込みも、`~/.claude/skills` の
直下のフォルダを、`orchestrate` や `synced/`・`.trash/` まで含めて `~/.agents/skills` へ写す。写した SKILL.md では、
単語としての `claude`（`Claude Code`・`claude-code` など）が `Codex` に、`CLAUDE.md` が `AGENTS.md` に置き換わる（`~/.claude/` も `~/.Codex/` になる）。
取り込みは同じ名前のフォルダやリンクがあれば写さないので、写したものは古いまま残り、このロールのリンクも上書きされない
（[openai/codex#55903](https://github.com/openai/codex/issues/55903)）。一方、取り込める項目を数えるときはリンクを
フォルダとみなさないので、リンクにした skill も Import の画面に取り込める項目として出続ける。skill はこのロールのリンクで渡し、
取り込まない。取り込むと、手で取り込んでも自動更新でも、退避した `orchestrate`・`synced/`・`.trash/` の写しがまた写される。
取り込みが写した skill は、次の順に片付ける。先に自動更新を止めないと、退避した写しが次の自動更新で戻る。

1. Settings → Import の自動更新（文書の「Keep imported work in sync」）を切るか、取り込む項目から skill を外す
2. `~/.agents/skills` にある、取り込みが写したフォルダ（写した skill と `orchestrate`・`synced/`・`.trash/`）を `evacuate` で退避する
3. プレイブックを流す

取り込みは skill のほかにも次のものを写し、どれも Codex で効く。上の 1. で自動更新を切ってから片付ける。

| 取り込みの項目 | 写す先                                                                     | 片付け                                                                                                                                                                      |
| -------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CONFIG         | `~/.codex/config.toml` の `[shell_environment_policy]`                     | 節ごと消す。`settings.json` の `env` から `inherit = "core"` で写すので、Codex のシェルが引き継ぐ環境変数が PATH・HOME・LANG など 11 個に絞られる                           |
| HOOKS          | `~/.codex/hooks.json` と `~/.codex/hooks/`（スクリプトの写し）             | プレイブックが `hooks.json` を書き換えた後に `~/.codex/hooks/` を `evacuate` で退避し、Codex で hook を信頼し直す。先に退避すると、古い `hooks.json` が無いスクリプトを指す |
| projects       | 各リポジトリ直下の `AGENTS.md`（`.claude/CLAUDE.md` を語を置き換えた写し） | `evacuate` で退避する。取り込みは無いか空のときだけ書くので、残すと古いまま読まれ続ける                                                                                     |

取り込みは `hooks.json` があれば書かないので、このロールが置いたものは上書きされない。

ブラウザ版 ChatGPT はローカルファイルを自動では読み込まない。
全チャットに適用する指示は Settings → Personalization の Custom instructions に設定する。
ローカルの `AGENTS.md` とは自動同期されない。

仕様: [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[デスクトップの Personalization](https://learn.chatgpt.com/docs/app/settings)、
[ChatGPT のカスタム指示](https://learn.chatgpt.com/docs/personalize)、
[skill の置き場](https://learn.chatgpt.com/docs/build-skills)、
[ほかのエージェントからの取り込み](https://learn.chatgpt.com/docs/import)。

## Claude Code のキャラクター

応答のキャラクターは `ansible/roles/claude/files/characters/` から 1 つ選び、
`~/.claude/rules/character.md` に置く。既定は `zundamon`、`none` でキャラクターを使わない。

まだ選んでいなければ、プレイブック（`install` を含む）がロールを流す前に名前を聞く。Enter で既定になる。
選んだキャラクターは `~/.local/state/dotfiles/claude-character.json`（`XDG_STATE_HOME` があればその下）に
記録され、次からは聞かずにそれを使う。選んでいたキャラクターのファイルを改名・削除すると、もう一度聞く。
新しいセッションから効く。

端末が無いときは聞かずに既定を選び、選んだものとして記録する。次に端末から流しても聞かない。
改名・削除で聞き直す場面でも、端末が無ければ既定に置き換え、そのことを表示する。

今のキャラクターと選べるものは `dotfiles character` で見る。選び直すときは `dotfiles character set` に名前を渡す。
名前を省くと一覧から聞く（Enter で今のまま）。

```sh
dotfiles character set pico
```

プレイブックに `-e claude_character=<名前>` を渡しても選べる。

キャラクターを足すときは次に従う。

- ファイル名は英小文字・数字・`-` だけにする。それ以外の名前は記録に残しても読めないため、
  選択肢に出さず、名前を渡してもプレイブックが止める
- `characters/zundamon.md` と同じく「プロフィール」「文末と言い回し」「場面ごとの反応」の節を書く。
  振る舞いの規則は `files/AGENTS.md` の「場面ごとの振る舞い」にあり、キャラクターのファイルは声だけを持つ
- 「場面ごとの反応」の場面の名前は `AGENTS.md` の表と揃える。反応の言葉が要らない場面は「入れない」と書く

## Claude Code のプラグイン

`claude` ロールは、プラグインとそのマーケットプレイスを `~/.claude/settings.json` の `enabledPlugins` と
`extraKnownMarketplaces` に宣言する。宣言は `ansible/roles/claude/vars/main.yml` の `claude_plugin_settings` にあり、
`files/settings.json` の後に重ねる。

| プラグイン                                                                                                                                                  | 中身                                                                                                                                                                                 | 版                                                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| `yomiyasu@yomiyasu`（[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)）                                                                              | AI が書いた日本語を推敲する skill。名前を出したとき（`/yomiyasu:yomiyasu`、「yomiyasu で推敲して」）、スキルでの推敲をはっきり頼んだとき、CLAUDE.md などで使うよう指示したときに動く | `claude_yomiyasu_version`（タグで固定）                     |
| `frontend-design@dotfiles`（[anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design)） | UI を新しく作るときや作り直すときに、見た目の方向づけを示す skill                                                                                                                    | `claude_frontend_design_skill_url` の SHA（コミットで固定） |

anthropics/claude-plugins-official にはタグが無く、マーケットプレイスの `ref` では固定できない。そこでプレイブックは
`~/.local/share/dotfiles/claude-marketplace/`（`XDG_DATA_HOME` があればその下）に `dotfiles` という名前の
マーケットプレイスを書き、そこで frontend-design の取得元をコミット SHA で指す（vars の `claude_marketplace`）。
Claude Code はこのディレクトリを写さずにその場で読むので、残しておく。

どの文章を `yomiyasu:yomiyasu` で推敲するかは、共有のグローバル指示（`files/AGENTS.md`）の「手順を持つ skill」の節が決める。
この節は Codex のグローバル指示にも入り、Codex には `codex` ロールが同じ版の skill を置く
（[Codex / ChatGPT のグローバル指示](#codex--chatgpt-のグローバル指示)）。

プレイブックはプラグインを取得しない。宣言を読んだ Claude Code が、セッションの開始後にマーケットプレイスを
登録して（github のものはクローンして）プラグインを取得する。宣言だけの状態では、マーケットプレイスがまだ登録されて
いないので、`claude plugin install` も `claude plugin marketplace update` も not found で失敗する。セッションを待たずに
入れるときは、宣言と同じ source でマーケットプレイスを足してから入れる。

```sh
claude plugin marketplace add 'nanaism/yomiyasu#<claude_yomiyasu_version の値>'
claude plugin install yomiyasu@yomiyasu
claude plugin marketplace add "${XDG_DATA_HOME:-$HOME/.local/share}/dotfiles/claude-marketplace"
claude plugin install frontend-design@dotfiles
```

前に frontend-design の SKILL.md を `~/.claude/skills/frontend-design/` へ写していたマシンでは、そのディレクトリが残り、
同じ skill が 2 つ並ぶ。残っていればプレイブックが知らせるので、プラグインが入ったのを `claude plugin list` で確かめてから、
`evacuate` で取り除く。

```sh
evacuate -n frontend-design-skill ~/.claude/skills/frontend-design
```

yomiyasu の lint と check は Python 3 の標準ライブラリで動き、skill の `allowed-tools` により確認なしで実行される。
ファイルを渡したときに読むのは作業フォルダの中のものだけで、作業フォルダの外のものと、作業フォルダからのパスに
点で始まる部分（`.claude/` など）を含むものは、読まずに終了コード 2 で止まる。標準入力からは読める。
check は原稿の写しと記録を git の最上位の `.yomiyasu/`（環境変数 `YOMIYASU_STATE_DIR` で変えられる）に書き、
既定の場所では `.gitignore` も置くので git の管理には入らない。Python が無いと、検査を飛ばして目視で点検する。

新しい版の公開から 1 週間たつと `dotfiles check` が知らせる。`claude_yomiyasu_version` を書き換えてプレイブックを流すと、
取得済みのマーケットプレイスの source が宣言と食い違い、プラグインは読み込まれなくなる（`claude plugin list` が
`failed to load` と `added but ignored` を出す）。前に別の版や `ref` なしで足していたマシンに初めて配ったときも同じになる。
宣言の版でマーケットプレイスを足し直してから、プラグインをその版に合わせる。足し直すだけでは版は変わらず、
足し直す前の `claude plugin update` は not found で失敗する。合ったかは `claude plugin list` の Version で確かめる。

```sh
claude plugin marketplace add 'nanaism/yomiyasu#<claude_yomiyasu_version の値>'
claude plugin update yomiyasu@yomiyasu
```

Codex の側は手で揃えなくてよい。プレイブックが clone を新しいタグへ checkout し直し、リンクはそのまま新しい版を指す。

frontend-design は、固定した SKILL.md が上流で変わってから 1 週間たつと `dotfiles check` が知らせる（SKILL.md 以外の
ファイルの変更は知らせない）。`claude_frontend_design_skill_url` の SHA を書き換えてプレイブックを流すと、
marketplace.json の `sha` が変わる。宣言のパスは変わらないので、yomiyasu のように読み込まれなくなることはない。
続けてプラグインを更新する。

```sh
claude plugin update frontend-design@dotfiles
```

`plugin.json` に `version` があれば、プラグインの版はそれで決まる（今の固定先は 1.1.1）。上流がそれを上げずに
SKILL.md だけを変えていると、update は `already at the latest version` と出て何もしない。そのときは入れ直す。
プレイブックは、`~/.claude/plugins/installed_plugins.json` の `gitCommitSha` が固定の SHA と違えば、そのことを知らせる。

```sh
claude plugin uninstall frontend-design@dotfiles
claude plugin install frontend-design@dotfiles
```

Codex の側は手で揃えなくてよい。プレイブックが同じ URL の SKILL.md を取り直す。

`/plugin` で無効にしても、`enabledPlugins` はリポジトリ側の値なので、プレイブックを流すたびに有効に戻る。
外すときは `claude_plugin_settings` から yomiyasu の 2 項目を消し、`claude plugin marketplace remove yomiyasu` を流す。
取得済みなら、プラグインのアンインストールと、配置先の `~/.claude/settings.json` の 2 つのキーの削除まで行われる。
一度も取得していなければ remove は not found で失敗するので、配置先から `extraKnownMarketplaces.yomiyasu` と
`enabledPlugins` の `yomiyasu@yomiyasu` を手で消す。宣言が残ると、次のセッションでまた取得される。
Codex の側も外すときは、`ansible/roles/codex/tasks/skills.yml` から名前に yomiyasu を含む 4 つのタスクを、
`ansible/roles/codex/vars/main.yml` から `codex_yomiyasu_version`・`codex_yomiyasu_dir` を消す。
`skills.yml` の取り込みと `codex_skills_dir` は、Claude Code と共有する skill（[Codex / ChatGPT のグローバル指示](#codex--chatgpt-のグローバル指示)）が
使うので残す。配置先の `~/.agents/skills/yomiyasu`（リンク）と `~/.local/share/yomiyasu`（`XDG_DATA_HOME` があればその下）は
`evacuate` で退避する。yomiyasu のタスクを残したまま `claude_yomiyasu_version` を消すと、codex ロールが版を読めずに止まる。
両方から外すときは、`files/AGENTS.md` の「手順を持つ skill」にある yomiyasu の行も消す。残すと、無い skill で推敲するよう指示し続ける。

frontend-design を外すときは、vars から `claude_frontend_design_skill_url`・`claude_frontend_design_source`・
`claude_marketplace_dir`・`claude_marketplace` と、`claude_plugin_settings` の `dotfiles` と `frontend-design@dotfiles` を消す。
URL が残ると、`dotfiles check` が更新を知らせ続ける。ただし Codex の側に残すときは、`codex` ロールがこの URL を読むので
`claude_frontend_design_skill_url` は残す。tasks からも、Check the pinned frontend-design URL から
Write the dotfiles marketplace までの 3 つと、末尾の Check if installed_plugins.json exists から
Report the old frontend-design skill までの 5 つを消す。そのうえで `claude plugin marketplace remove dotfiles` を流す。
登録済みなら、yomiyasu と同じく、プラグインのアンインストールと 2 つのキーの削除まで行われる。一度も登録していなければ
remove は not found で失敗するので、配置先から `extraKnownMarketplaces.dotfiles` と `enabledPlugins` の
`frontend-design@dotfiles` を手で消す。marketplace.json のディレクトリは残るので、`evacuate` で取り除く。

```sh
evacuate -n claude-marketplace "${XDG_DATA_HOME:-$HOME/.local/share}/dotfiles/claude-marketplace"
```

Codex の側も外すときは、`ansible/roles/codex/tasks/skills.yml` から名前に frontend-design を含む 2 つのタスクを、
`ansible/roles/codex/vars/main.yml` から `codex_frontend_design_skill_url`・`codex_frontend_design_dir` と、
`codex_shared_skills`・`codex_shared_skill_sources` の frontend-design を消す。codex のタスクを残したまま
`claude_frontend_design_skill_url` を消すと、codex ロールが URL を読めずに止まる。配置先のリンクと取った SKILL.md は残るので、
`evacuate` で取り除く。

```sh
evacuate -n codex-frontend-design ~/.agents/skills/frontend-design "${XDG_DATA_HOME:-$HOME/.local/share}/dotfiles/codex-skills/frontend-design"
```

## AWS CLI

`awscli` ロールは AWS CLI v2 を固定バージョンでインストールする。公式の `install.sh` に版を渡し、
`~/.local/share/aws-cli`（`XDG_DATA_HOME` があればその下）へ入れて、`~/.local/bin/aws` から起動する。
Linux では、`install.sh` が使う `unzip` と `gpg` を先に sudo でパッケージから入れる。

`~/.local/bin` は PATH の末尾にあるので、Homebrew や OS のパッケージで入れた別の `aws`
（`/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin`、`/snap/bin` など）があると、そちらが使われる。
固定した版を使うときは、別の `aws` を取り除く。

`aws update` などで固定より新しい版が入っていれば、そのまま使う。固定より古い版へ戻すときは、
`~/.local/share/aws-cli` と `~/.local/bin/aws`、`~/.local/bin/aws_completer` を取り除いてからプレイブックを流す。
