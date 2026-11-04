// 最初の画面に何が入っているかを測る。ファイルの中身に続けて呼び出しを 1 行足し、ブラウザで実行する。
//
//   await uiAuditArea({item: '.result-card', regions: {h1: 'main h1', lede: '.lede', stats: '.stats', promo: '.featured'}});
//   await uiAuditArea({item: '.result-card', frame: {width: 390, height: 844}});
//
// item は一覧の 1 件を指すセレクタ、regions は見出し領域の内訳である。chrome はサイト共通のナビのセレクタで、
// 省くと main などの外にある header と nav を使う。frame を渡すと、そのページを同一オリジンの iframe で開いて
// 幅を固定する。ウィンドウの幅を変えられないときに使う。
window.uiAuditArea = async ({
  item,
  regions = {},
  chrome,
  frame,
  settleMs = 1500,
  timeoutMs = 15000,
}) => {
  const measure = (win) => {
    const doc = win.document;
    win.scrollTo(0, 0);
    const vw = win.innerWidth;
    const vh = win.innerHeight;
    // 非表示のタブは幅が 0 で、どの要素も見えない扱いになり、誤った位置を返す。
    if (vw === 0)
      return {
        error: "ビューポートの幅が 0。タブを前面に出すか、frame で幅を指定する",
      };
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = win.getComputedStyle(el);
      return (
        r.width > 0 &&
        r.height > 0 &&
        s.visibility !== "hidden" &&
        s.display !== "none"
      );
    };
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return {
        top: Math.round(r.top),
        bottom: Math.round(r.bottom),
        left: r.left,
        right: r.right,
      };
    };
    const nameOf = (el) =>
      [el.tagName.toLowerCase(), String(el.className).split(/\s+/)[0]]
        .filter(Boolean)
        .join(".");
    const share = (px) => +(Math.max(0, Math.min(px, vh)) / vh).toFixed(2);

    // main や article の中の header は内容の一部で、サイト共通の枠ではない。
    const pageLevel = (el) =>
      !el.parentElement.closest("main, article, section, aside");
    const chromeEls = [...doc.querySelectorAll(chrome ?? "header, nav")].filter(
      (el) => visible(el) && (chrome || pageLevel(el)),
    );
    const footers = [...doc.querySelectorAll("footer")].filter(pageLevel);
    const inChrome = (el) =>
      [...chromeEls, ...footers].some((c) => c.contains(el));
    const navBottom = Math.max(
      0,
      ...chromeEls.map((e) => box(e).bottom).filter((b) => b <= vh / 2),
    );

    // 宣伝パネルの項目を一覧の先頭と数えないよう、親ごとに分け、最も多い親を一覧とする。
    // li > .card のように 1 件ずつ包まれた項目だけを、複数の項目を持つ階層まで束ね直す。
    const matched = [...(item ? doc.querySelectorAll(item) : [])].filter(
      visible,
    );
    const groups = new Map();
    const add = (key, el) => groups.set(key, [...(groups.get(key) ?? []), el]);
    for (const el of matched) add(el.parentElement, el);
    for (let depth = 0; depth < 3; depth++) {
      for (const [parent, els] of [...groups]) {
        if (els.length > 1 || !parent.parentElement) continue;
        groups.delete(parent);
        add(parent.parentElement, els[0]);
      }
    }
    const ranked = [...groups.entries()].sort(
      (a, b) => b[1].length - a[1].length,
    );
    const items = ranked[0]?.[1] ?? [];
    const inView = items.map(box);
    const listTop = inView.length
      ? Math.min(...inView.map((b) => b.top))
      : null;

    const controls = [
      ...doc.querySelectorAll(
        'input:not([type="hidden"]),select,textarea,button,[role="button"],[role="tab"],[role="combobox"]',
      ),
    ].filter((el) => visible(el) && !inChrome(el));
    const firstControl = controls.sort((a, b) => box(a).top - box(b).top)[0];

    const parts = {};
    const spans = [];
    for (const [name, selector] of Object.entries(regions)) {
      const el = [...doc.querySelectorAll(selector)].find(visible);
      if (!el) {
        parts[name] = null;
        continue;
      }
      const b = box(el);
      parts[name] = {
        top: b.top,
        height: b.bottom - b.top,
        shareOfScreen: share(b.bottom - b.top),
      };
      spans.push([
        Math.max(b.top, navBottom),
        Math.min(b.bottom, listTop ?? b.bottom),
      ]);
    }
    // 横に並ぶ領域の高さを足すと重なりを二重に数えるので、縦の区間の和集合を取る。
    const covered = () => {
      let total = 0;
      let end = -Infinity;
      for (const [top, bottom] of spans.sort((a, b) => a[0] - b[0])) {
        const from = Math.max(top, end);
        if (bottom > from) {
          total += bottom - from;
          end = bottom;
        }
      }
      return total;
    };

    const warnings = [];
    if (item && !matched.length)
      warnings.push("item のセレクタに当たる要素が見えていない");
    if (items.length < matched.length)
      warnings.push(
        `item に当たった ${matched.length} 件のうち ${items.length} 件を一覧とした。otherItemGroups を確かめ、節に分かれた一覧ならセレクタを節ごとに渡す`,
      );

    return {
      path: win.location.pathname,
      viewport: [vw, vh],
      documentHeight: doc.documentElement.scrollHeight,
      navBottom,
      firstControl: firstControl
        ? { top: box(firstControl).top, tag: nameOf(firstControl) }
        : null,
      list: {
        top: listTop,
        screensDown: listTop === null ? null : +(listTop / vh).toFixed(2),
        items: items.length,
        matched: matched.length,
        fullyInFirstScreen: inView.filter(
          (b) =>
            b.top >= navBottom &&
            b.bottom <= vh &&
            b.left >= 0 &&
            b.right <= vw,
        ).length,
        partlyInFirstScreen: inView.filter((b) => b.top < vh && b.bottom > vh)
          .length,
      },
      otherItemGroups: ranked.slice(1, 6).map(([parent, els]) => ({
        parent: nameOf(parent),
        n: els.length,
        top: box(els[0]).top,
      })),
      parts,
      gapsAndUnnamed:
        listTop === null ? null : Math.max(0, listTop - navBottom) - covered(),
      warnings,
    };
  };

  if (!frame) return measure(window);

  const iframe = document.createElement("iframe");
  iframe.style.cssText = `position:fixed;left:0;top:0;width:${frame.width}px;height:${frame.height}px;border:0;opacity:0;pointer-events:none`;
  const loaded = new Promise((resolve, reject) => {
    iframe.addEventListener("load", resolve, { once: true });
    setTimeout(
      () => reject(new Error(`${timeoutMs}ms 待っても iframe が読み込めない`)),
      timeoutMs,
    );
  });
  iframe.src = location.href;
  document.body.append(iframe);
  try {
    await loaded;
    await new Promise((resolve) => setTimeout(resolve, settleMs));
    // 表示を拒否された iframe は別オリジンのエラーページになり、document を読むと例外になる。
    try {
      iframe.contentWindow.document.body;
    } catch {
      return {
        error:
          "iframe を読めない。X-Frame-Options か CSP の frame-ancestors を確かめる",
      };
    }
    return measure(iframe.contentWindow);
  } finally {
    iframe.remove();
  }
};
