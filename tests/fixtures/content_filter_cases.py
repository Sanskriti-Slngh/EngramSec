from __future__ import annotations


CONTENT_FILTER_CASES = [
    (
        "view_count_only",
        '<main><article><h1>Article Alpha</h1><p>Stable body</p>'
        '<span><i class="icon-eye"></i>41</span></article></main>',
        '<main><article><h1>Article Alpha</h1><p>Stable body</p>'
        '<span><i class="icon-eye"></i>42</span></article></main>',
        True,
    ),
    (
        "article_beside_view_counter",
        '<main><div><i class="icon-eye"></i><span>41</span>'
        '<article><h1>Article Alpha</h1><p>Alpha body</p></article></div></main>',
        '<main><div><i class="icon-eye"></i><span>42</span>'
        '<article><h1>Article Beta</h1><p>Beta body</p></article></div></main>',
        False,
    ),
    (
        "meaningful_record_date",
        '<main><article><h1>Record Alpha</h1>'
        '<time datetime="2026-10-28">Record date: 2026-10-28</time></article></main>',
        '<main><article><h1>Record Alpha</h1>'
        '<time datetime="2026-10-29">Record date: 2026-10-29</time></article></main>',
        False,
    ),
    (
        "explicit_cosmetic_clock",
        '<main><h1>Status</h1><p>Stable</p><time data-volatile>13:40</time></main>',
        '<main><h1>Status</h1><p>Stable</p><time data-volatile>13:41</time></main>',
        True,
    ),
    (
        "carousel_content",
        '<main><h1>Featured</h1><section class="carousel"><p>Campaign Alpha</p></section></main>',
        '<main><h1>Featured</h1><section class="carousel"><p>Campaign Beta</p></section></main>',
        False,
    ),
]
