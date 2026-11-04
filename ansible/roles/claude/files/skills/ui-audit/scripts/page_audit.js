// 開いているページの文字、コントラスト、動かない操作部、見た目の型、和文の組版を集計する。
// ファイルの中身をそのままブラウザで実行すると、結果のオブジェクトが返る。ページの状態は変えない。
(() => {
  // 非表示のタブは幅が 0 で、どの要素も見えない扱いになり、0 件という誤った結果を返す。
  if (innerWidth === 0)
    return {
      error:
        "ビューポートの幅が 0。タブを前面に出すか、幅を指定してから実行する",
    };

  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return (
      r.width > 0 &&
      r.height > 0 &&
      s.visibility !== "hidden" &&
      s.display !== "none"
    );
  };
  const label = (el) =>
    (
      el.title ||
      el.innerText ||
      el.getAttribute("aria-label") ||
      el.placeholder ||
      el.value ||
      el.name ||
      el.tagName
    )
      .trim()
      .slice(0, 28);

  // getComputedStyle は oklch() や color() のまま返すことがあるので、1 ピクセル描いて sRGB に直す。
  const ctx = Object.assign(document.createElement("canvas"), {
    width: 1,
    height: 1,
  }).getContext("2d", {
    willReadFrequently: true,
  });
  const colors = new Map();
  const parse = (c) => {
    if (!colors.has(c)) {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = c;
      ctx.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
      colors.set(c, { r, g, b, a: a / 255 });
    }
    return colors.get(c);
  };
  const over = (f, b) => ({
    r: f.r * f.a + b.r * (1 - f.a),
    g: f.g * f.a + b.g * (1 - f.a),
    b: f.b * f.a + b.b * (1 - f.a),
    a: 1,
  });
  const lin = (v) => {
    v /= 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const backgroundOf = (el) => {
    const chain = [];
    for (let e = el; e; e = e.parentElement) chain.push(e);
    let base = { r: 255, g: 255, b: 255, a: 1 };
    let image = false;
    for (const e of chain.reverse()) {
      const s = getComputedStyle(e);
      if (s.backgroundImage !== "none") image = true;
      const c = parse(s.backgroundColor);
      if (c.a > 0) {
        base = over(c, base);
        if (c.a === 1) image = s.backgroundImage !== "none";
      }
    }
    return { base, image };
  };
  const opacityOf = (el) => {
    let o = 1;
    for (let e = el; e; e = e.parentElement) o *= +getComputedStyle(e).opacity;
    return o;
  };
  const media = [...document.querySelectorAll("img,video,canvas")]
    .filter(visible)
    .map((m) => ({ m, r: m.getBoundingClientRect() }));
  const overMedia = (el) => {
    const b = el.getBoundingClientRect();
    const x = b.left + b.width / 2;
    const y = b.top + b.height / 2;
    return media.some(
      ({ m, r }) =>
        !el.contains(m) &&
        x >= r.left &&
        x <= r.right &&
        y >= r.top &&
        y <= r.bottom,
    );
  };

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  const rows = [];
  while (walker.nextNode()) {
    const t = walker.currentNode.textContent.trim();
    const el = walker.currentNode.parentElement;
    if (
      !t ||
      !el ||
      seen.has(el) ||
      ["SCRIPT", "STYLE", "NOSCRIPT"].includes(el.tagName)
    )
      continue;
    seen.add(el);
    if (visible(el)) rows.push({ el, t, s: getComputedStyle(el) });
  }

  const low = {};
  const families = {};
  const counts = {
    under14: 0,
    under12: 0,
    atMost10: 0,
    uppercase: 0,
    palt: 0,
    contrastMeasured: 0,
    contrastSkipped: 0,
  };
  const latinCaps = [];
  for (const { el, t, s } of rows) {
    const size = parseFloat(s.fontSize);
    if (size < 14) counts.under14++;
    if (size < 12) counts.under12++;
    if (size <= 10) counts.atMost10++;
    if (s.textTransform === "uppercase") counts.uppercase++;
    if (s.fontFeatureSettings.includes("palt")) counts.palt++;
    const family = s.fontFamily.split(",")[0].replace(/"/g, "");
    families[family] = (families[family] || 0) + 1;
    if (
      s.textTransform === "uppercase" ||
      /^[A-Z][A-Z0-9 .·&/—-]{2,}$/.test(t)
    ) {
      latinCaps.push(el.closest("[lang]")?.lang || "");
    }

    // background-clip: text の文字は color が透明で、背景の画像が見た目の色になる。
    // 画像の上の文字は下の色が決まらないので測らない。無効な操作部は WCAG 1.4.3 の対象外である。
    const fg = parse(s.webkitTextFillColor || s.color);
    const { base, image } = backgroundOf(el);
    if (
      fg.a === 0 ||
      image ||
      overMedia(el) ||
      el.closest(':disabled, [aria-disabled="true"]')
    ) {
      counts.contrastSkipped++;
      continue;
    }
    counts.contrastMeasured++;
    // 基準は https://www.w3.org/TR/WCAG22/#contrast-minimum である。
    // 祖先の opacity は文字にだけ掛ける。背景ごと薄まる要素では、実際より低い値が出る。
    const c = ratio(over({ ...fg, a: fg.a * opacityOf(el) }, base), base);
    const large = size >= 24 || (size >= 18.66 && +s.fontWeight >= 700);
    if (c < (large ? 3 : 4.5)) {
      const key = `${String(el.className).slice(0, 40)}|${size}|${c.toFixed(2)}`;
      low[key] = low[key] || {
        text: t.slice(0, 28),
        size,
        ratio: +c.toFixed(2),
        n: 0,
      };
      low[key].n++;
    }
  }

  // React の内部プロパティを読む。無い要素は判定せず unjudged に返す（React の外の部品か、水和の前である）。
  const propsOf = (el) => {
    const k = Object.keys(el).find(
      (x) =>
        x.startsWith("__reactProps") || x.startsWith("__reactEventHandlers"),
    );
    return k ? el[k] : null;
  };
  const all = [...document.querySelectorAll("body *")];
  const react = all.some(propsOf);
  const hasClick = (p) =>
    Boolean(
      p && (p.onClick || p.onMouseDown || p.onPointerDown || p.onPointerUp),
    );
  const inputButtons =
    'input[type="button"],input[type="submit"],input[type="reset"],input[type="image"]';
  const controls = {
    react,
    unjudged: null,
    deadButtons: null,
    delegatedButtons: null,
    deadFields: null,
  };
  if (react) {
    const buttons = [
      ...document.querySelectorAll(
        `button,[role="button"],a:not([href]),${inputButtons}`,
      ),
    ].filter((b) => visible(b) && !b.disabled);
    const judged = buttons.filter(propsOf);
    controls.unjudged = buttons.filter((b) => !propsOf(b)).map(label);
    // action も onSubmit も無い form は、送信しても何も処理しない。
    const submits = (form) =>
      form &&
      (form.hasAttribute("action") ||
        propsOf(form)?.onSubmit ||
        propsOf(form)?.action);
    // type の無い button も b.type は submit を返すので、属する form を見る。
    const native = (b) =>
      (b.type === "submit" && submits(b.form)) ||
      b.hasAttribute("popovertarget") ||
      b.hasAttribute("commandfor");
    const unbound = judged.filter((b) => !native(b) && !hasClick(propsOf(b)));
    const delegated = (b) => {
      for (let e = b.parentElement; e; e = e.parentElement)
        if (hasClick(propsOf(e))) return true;
      return false;
    };
    controls.deadButtons = unbound.filter((b) => !delegated(b)).map(label);
    controls.delegatedButtons = unbound.filter(delegated).map(label);
    controls.deadFields = [
      ...document.querySelectorAll(
        'input:not([type="hidden"]),select,textarea',
      ),
    ]
      .filter((f) => {
        const p = propsOf(f);
        return (
          visible(f) &&
          !f.matches(inputButtons) &&
          !f.disabled &&
          !f.readOnly &&
          !submits(f.form) &&
          p &&
          !p.onChange &&
          !p.onInput
        );
      })
      .map(label);
  }
  controls.readOnlyFields = [
    ...document.querySelectorAll('input:not([type="hidden"]),textarea'),
  ]
    .filter((f) => visible(f) && f.readOnly)
    .map(label);
  controls.placeholderLinks = [
    ...document.querySelectorAll(
      'a[href="#"],a[href=""],a[href^="javascript:"]',
    ),
  ].map(label);

  const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")]
    .filter(visible)
    .map((h) => {
      const s = getComputedStyle(h);
      const size = parseFloat(s.fontSize);
      const text = h.innerText.replace(/\s+/g, " ").trim();
      return {
        tag: h.tagName.toLowerCase(),
        text: text.slice(0, 40),
        kuten: /[。．]$/.test(text),
        twoBeat: /、.+。$/.test(text),
        size,
        letterSpacingEm:
          s.letterSpacing === "normal"
            ? 0
            : +(parseFloat(s.letterSpacing) / size).toFixed(3),
        lineHeight:
          s.lineHeight === "normal"
            ? null
            : +(parseFloat(s.lineHeight) / size).toFixed(2),
        wordBreak: s.wordBreak,
      };
    });

  const rules = {
    unreadableSheets: 0,
    focusVisible: 0,
    outlineNone: 0,
    reducedMotion: 0,
    keyframes: 0,
    transitionAll: 0,
  };
  const scan = (list) => {
    for (const r of list) {
      if (r.type === CSSRule.KEYFRAMES_RULE) rules.keyframes++;
      if (r.conditionText?.includes("prefers-reduced-motion"))
        rules.reducedMotion++;
      if (r.selectorText?.includes(":focus-visible")) rules.focusVisible++;
      if (
        /(^|\s)(none|0(px)?|transparent)(\s|$)/.test(
          `${r.style?.outline} ${r.style?.outlineStyle}`,
        )
      )
        rules.outlineNone++;
      if (r.style?.transitionProperty === "all") rules.transitionAll++;
      if (r.cssRules) scan(r.cssRules);
    }
  };
  for (const sheet of document.styleSheets) {
    try {
      scan(sheet.cssRules);
    } catch {
      rules.unreadableSheets++;
    }
  }

  const text = document.body.innerText;
  const count = (re) => (text.match(re) || []).length;
  const bodyStyle = getComputedStyle(document.body);
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"]`)?.content ?? null;

  return {
    page: {
      path: location.pathname,
      title: document.title,
      description: meta("description"),
      lang: document.documentElement.lang,
      favicons: [...document.querySelectorAll('link[rel~="icon"]')].map(
        (l) => l.href,
      ),
      viewport: [innerWidth, innerHeight],
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    },
    text: {
      elements: rows.length,
      ...counts,
      latinCapsLabels: latinCaps.length,
      latinCapsWithoutEnLang: latinCaps.filter((l) => !l.startsWith("en"))
        .length,
      families,
      bodyFontFamily: bodyStyle.fontFamily,
      bodyFontFeatures: bodyStyle.fontFeatureSettings,
    },
    lowContrastTotal: Object.values(low).reduce((n, x) => n + x.n, 0),
    lowContrast: Object.values(low)
      .sort((a, b) => b.n - a.n)
      .slice(0, 10),
    controls,
    headings: {
      total: headings.length,
      kuten: headings.filter((h) => h.kuten).length,
      twoBeat: headings.filter((h) => h.twoBeat).length,
      list: headings.slice(0, 30),
    },
    marks: {
      middleDotLatin: count(/·/g),
      middleDotKana: count(/・/g),
      spacedSlash: count(/ \/ /g),
      straightQuotes: count(/"/g),
      desuMasu: count(/(です|ます|ました|でした|ません|ください)。/g),
      plainForm: count(/(である|だ|する|(?<![まで])した|いる|ない)。/g),
    },
    looks: {
      gradientText: all
        .filter((e) => getComputedStyle(e).backgroundClip === "text")
        .map((e) => ({
          text: e.innerText.slice(0, 16),
          background: getComputedStyle(e).backgroundImage.slice(0, 90),
        })),
      glass: all.filter(
        (e) => (getComputedStyle(e).backdropFilter || "none") !== "none",
      ).length,
      infiniteAnimations: document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations === Infinity)
        .length,
    },
    rules,
  };
})();
