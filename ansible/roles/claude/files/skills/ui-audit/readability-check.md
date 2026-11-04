# 読みやすさの点検

`page_audit.js` の結果を土台にする。フォーカスと動きは数字だけでは分からないので、実際に操作して確かめる。

## 文字とコントラスト

| 見るもの     | 結果のキー                                      | 判断                                                                                                                    |
| ------------ | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 小さな文字   | `text.under14`、`text.under12`、`text.atMost10` | 和文の基準は [japanese.md](japanese.md) にある                                                                          |
| コントラスト | `lowContrastTotal`、`lowContrast`               | AA の基準は本文で 4.5:1、大きな文字で 3:1 である（[WCAG 2.2 の 1.4.3](https://www.w3.org/TR/WCAG22/#contrast-minimum)） |
| 測れない文字 | `text.contrastSkipped`                          | 背景画像や画像の上の文字、透明な文字、無効な部品である。件数が多いページはスクリーンショットで見る                      |
| トークンの組 | `contrast.py`                                   | ソースがあれば色の組を表にする。透明度のある色は背景に合成してから渡す                                                  |

`lowContrast` は候補である。祖先の `opacity` は文字にだけ掛けて計算するので、背景ごと薄まる要素では実際より低く出る。実画面で見てから欠陥と書く。

## フォーカス

1. Tab で操作部を順に辿り、フォーカスの位置が毎回見えるかを確かめる（[WCAG 2.2 の 2.4.7](https://www.w3.org/TR/WCAG22/#focus-visible)、Level AA）
2. `rules.outlineNone` が多く `rules.focusVisible` が少ないときは、`outline` を消したまま代わりの表示を出していない箇所を探す

## 動き

1. `looks.infiniteAnimations` で止まらない動きを数える。自動で 5 秒を超えて動き続けるものに止める手段が無ければ、[WCAG 2.2 の 2.2.2](https://www.w3.org/TR/WCAG22/#pause-stop-hide)（Level A）に当たる
2. `prefers-reduced-motion: reduce` を効かせて `page_audit.js` を流し直す。ブラウザの開発ツールのエミュレーションか、Playwright の `reducedMotion: 'reduce'` を使う。`looks.infiniteAnimations` が 0 になるかと、スクロール出現の要素が見えたままかを見る
3. 効かせられない環境では、`rules.reducedMotion` と `rules.keyframes` の数の差を手がかりにし、確かめられなかったと報告に書く

操作に応じた動きの抑制は [WCAG 2.2 の 2.3.3](https://www.w3.org/TR/WCAG22/#animation-from-interactions) で、Level AAA である。報告には当たる基準のレベルを添える。

JS が動くまで `opacity: 0` のままの要素は、基準によらず欠陥である。JS が失敗すると内容が見えない。

## はみ出し

`page.horizontalOverflow` が true なら、どの幅で横スクロールが出るかと、はみ出している要素を書く。

## CSS の規則の読み方

| キー                     | 意味                                                                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `rules.focusVisible`     | `:focus-visible` を含むセレクタの数                                                                                                |
| `rules.outlineNone`      | `outline` を `none`、`0`、`transparent` にしている規則の数                                                                         |
| `rules.reducedMotion`    | `prefers-reduced-motion` の `@media` の数                                                                                          |
| `rules.keyframes`        | `@keyframes` の数                                                                                                                  |
| `rules.transitionAll`    | `transition: all` の規則の数                                                                                                       |
| `rules.unreadableSheets` | 読めなかったスタイルシートの数。1 以上なら、ほかのキーの 0 は「無い」の証拠にならない。ソースがあれば `count_patterns.py` で数える |
