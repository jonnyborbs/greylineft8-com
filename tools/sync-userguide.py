#!/usr/bin/env python3
"""
sync-userguide.py
Converts /Users/jon/Developer/greylineft8/docs/user-manual.md into the
guide-content section of userguide.html, replacing everything between the
"<!-- ── CONTENT ── -->" and "</div><!-- /.guide-content -->" markers.

Usage:
    python3 tools/sync-userguide.py
"""

import re
import sys

MD_SOURCE = '/Users/jon/Developer/greylineft8/docs/user-manual.md'
HTML_TARGET = '/Users/jon/Developer/greylineft8-com/userguide.html'
CHANGELOG = '/Users/jon/Developer/greylineft8-com/changelog.html'


def escape(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


USED_IDS = set()


def unique_id(slug):
    """Return slug, suffixed if a previous heading already claimed it."""
    candidate, n = slug, 2
    while candidate in USED_IDS:
        candidate = f'{slug}-{n}'
        n += 1
    USED_IDS.add(candidate)
    return candidate


def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    return re.sub(r'-+', '-', text)


def inline(text):
    """Convert inline markdown to HTML (code, bold, italic, links)."""
    # Code spans first so inner * aren't processed
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape(m.group(1))}</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


BLOCK_STARTERS = ('- ', '> ', '```', '#### ', '### ', '## ', '| ')


def is_special(line):
    return (not line.strip() or
            line.strip() == '---' or
            any(line.startswith(p) for p in BLOCK_STARTERS) or
            re.match(r'^\d+\. ', line))


def collect_list_item(lines, start):
    """Collect a potentially multi-line list item starting at lines[start].
    Stops at blank lines, new top-level list items, block starters, or indented sub-items."""
    text = re.sub(r'^(?:-|\d+\.)\s+', '', lines[start]).strip()
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            break
        if line.startswith('- ') or re.match(r'^\d+\. ', line):
            break
        if any(line.startswith(p) for p in ('> ', '```', '#### ', '### ', '## ')):
            break
        if (line.strip().startswith('|') and i + 1 < len(lines) and
                re.match(r'^\s*\|[-| ]+\|', lines[i + 1])):
            break
        if re.match(r'^\s{2,}- ', line):  # indented sub-item
            break
        text += ' ' + line.strip()
        i += 1
    return text, i


def collect_sub_items(lines, start):
    """Collect indented sub-items (lines starting with 2+ spaces + '- ') into text strings."""
    sub_items = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not re.match(r'^\s{2,}- ', line):
            break
        # strip leading whitespace and '- '
        text = re.sub(r'^\s+-\s+', '', line).strip()
        i += 1
        # collect continuation lines (non-blank, not a new item of any kind)
        while i < len(lines):
            sl = lines[i]
            if not sl.strip():
                break
            if sl.startswith('- ') or re.match(r'^\d+\. ', sl):
                break
            if re.match(r'^\s{2,}- ', sl):
                break
            if any(sl.startswith(p) for p in ('> ', '```', '#### ', '### ', '## ')):
                break
            text += ' ' + sl.strip()
            i += 1
        sub_items.append(text)
    return sub_items, i


def parse_block(lines, indent='      '):
    """Parse a list of markdown lines into HTML block elements."""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.strip() == '---':
            i += 1
            continue

        # h4
        if line.startswith('#### '):
            h4_title = line[5:].strip()
            h4_slug = unique_id(slugify(h4_title))
            out.append(f'{indent}<h4 id="{h4_slug}">{inline(escape(h4_title))}</h4>')
            i += 1
            continue

        # Blockquote
        if line.startswith('> '):
            bq_lines = []
            while i < len(lines) and lines[i].startswith('> '):
                bq_lines.append(lines[i][2:])
                i += 1
            out.append(f'{indent}<blockquote>')
            out.extend(parse_block(bq_lines, indent + '  '))
            out.append(f'{indent}</blockquote>')
            continue

        # Fenced code block
        if line.startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(escape(lines[i]))
                i += 1
            i += 1
            out.append(f'{indent}<pre><code>' + '\n'.join(code_lines) + '</code></pre>')
            continue

        # Table
        if (line.strip().startswith('|') and i + 1 < len(lines) and
                re.match(r'^\s*\|[-| ]+\|', lines[i + 1] if i + 1 < len(lines) else '')):
            headers = [c.strip() for c in line.strip().strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(cells)
                i += 1
            out.append(f'{indent}<div class="table-wrap">')
            out.append(f'{indent}  <table>')
            out.append(f'{indent}    <thead><tr>' +
                       ''.join(f'<th>{inline(escape(h))}</th>' for h in headers) +
                       '</tr></thead>')
            out.append(f'{indent}    <tbody>')
            for row in rows:
                out.append(f'{indent}      <tr>' +
                            ''.join(f'<td>{inline(escape(c))}</td>' for c in row) +
                            '</tr>')
            out.append(f'{indent}    </tbody>')
            out.append(f'{indent}  </table>')
            out.append(f'{indent}</div>')
            continue

        # Unordered list
        if line.startswith('- '):
            out.append(f'{indent}<ul>')
            while i < len(lines) and lines[i].startswith('- '):
                item_text, i = collect_list_item(lines, i)
                sub_items, i = collect_sub_items(lines, i)
                if sub_items:
                    out.append(f'{indent}  <li>{inline(escape(item_text))}')
                    out.append(f'{indent}    <ul>')
                    for sub in sub_items:
                        out.append(f'{indent}      <li>{inline(escape(sub))}</li>')
                    out.append(f'{indent}    </ul>')
                    out.append(f'{indent}  </li>')
                else:
                    out.append(f'{indent}  <li>{inline(escape(item_text))}</li>')
            out.append(f'{indent}</ul>')
            continue

        # Ordered list
        if re.match(r'^\d+\. ', line):
            out.append(f'{indent}<ol>')
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                item_text, i = collect_list_item(lines, i)
                out.append(f'{indent}  <li>{inline(escape(item_text))}</li>')
            out.append(f'{indent}</ol>')
            continue

        # Paragraph — accumulate until blank line or block starter
        para_lines = []
        while i < len(lines) and lines[i].strip() and not is_special(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        text = ' '.join(para_lines)
        if text:
            out.append(f'{indent}<p>{inline(escape(text))}</p>')

    return out


def process_section(sec_text):
    """Convert a ## section block to HTML."""
    lines = sec_text.strip().split('\n')
    h2_match = re.match(r'## (\d+)\. (.+)', lines[0])
    credits_match = re.match(r'## (Credits)', lines[0])

    if h2_match:
        num = h2_match.group(1)
        title = h2_match.group(2).strip()
        slug = f'{num}-{slugify(title)}'
        h2_html = (f'      <h2><a href="#{slug}"><span class="section-num">{num}.</span>'
                   f' {inline(escape(title))}</a></h2>')
        section_id = slug
        comment = f'<!-- {num}. {title} -->'
    elif credits_match:
        section_id = 'credits'
        h2_html = '      <h2><a href="#credits">Credits</a></h2>'
        comment = '<!-- Credits -->'
    else:
        return ''

    out = [f'\n    {comment}']
    out.append(f'    <section class="guide-section" id="{section_id}">')
    out.append(h2_html)

    rest = '\n'.join(lines[1:]).strip()
    subsections = re.split(r'^(### .+)', rest, flags=re.MULTILINE)

    if subsections[0].strip():
        out.extend(parse_block(subsections[0].strip().split('\n')))

    i = 1
    while i < len(subsections):
        h3_title = subsections[i][4:].strip()
        h3_slug = unique_id(slugify(h3_title))
        out.append(f'      <h3 id="{h3_slug}"><a href="#{h3_slug}">'
                   f'{inline(escape(h3_title))}</a></h3>')
        if i + 1 < len(subsections):
            out.extend(parse_block(subsections[i + 1].strip().split('\n')))
        i += 2

    out.append('    </section>')
    return '\n'.join(out)


def latest_changelog_version():
    """The version marked Latest in changelog.html, the site's own source of truth."""
    try:
        with open(CHANGELOG, 'r') as f:
            m = re.search(r'<option value="[^"]*">([\d.]+)\s*—\s*Latest</option>', f.read())
    except OSError:
        return None
    return m.group(1) if m else None


def normalize(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = (text.replace('&amp;', '&').replace('&lt;', '<')
                .replace('&gt;', '>').replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', text).strip()


def check_links(html):
    """Report broken internal anchors and a table of contents that has drifted.

    The TOC lives outside the CONTENT markers, so the sync never touches it and
    it silently goes stale when a section is renamed or renumbered.
    """
    problems = []   # links that are actually broken
    notes = []      # wording drift, which may be deliberate

    ids = re.findall(r'id="([^"]+)"', html)
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    for dup in duplicates:
        problems.append(f'duplicate id: #{dup}')

    id_set = set(ids)
    for ref in sorted(set(re.findall(r'href="#([^"]+)"', html))):
        if ref not in id_set:
            problems.append(f'broken link: #{ref} has no matching id')

    toc_match = re.search(r'<ol class="toc-list">(.*?)</ol>', html, re.DOTALL)
    if not toc_match:
        problems.append('table of contents not found — check the toc-list markup')
    else:
        toc = [(href, normalize(label)) for href, label in
               re.findall(r'<li><a href="#([^"]+)">(.*?)</a></li>', toc_match.group(1))]
        headings = [(slug, f'{num}. {normalize(title)}') for slug, num, title in
                    re.findall(r'<h2><a href="#([^"]+)">'
                               r'<span class="section-num">(\d+)\.</span>(.*?)</a></h2>', html)]
        if len(toc) != len(headings):
            problems.append(f'table of contents has {len(toc)} entries '
                            f'but the guide has {len(headings)} sections')
        for (toc_slug, toc_label), (slug, label) in zip(toc, headings):
            if toc_slug != slug:
                problems.append(f'table of contents points at #{toc_slug} '
                                f'but that section is now #{slug} ("{label}")')
            elif toc_label != label:
                notes.append(f'table of contents reads "{toc_label}" '
                             f'where the section is titled "{label}"')

    return problems, notes


def main():
    with open(MD_SOURCE, 'r') as f:
        raw = f.read()

    version_match = re.search(r'^_For version (.+?)_', raw, re.MULTILINE)
    if version_match:
        version = version_match.group(1)
    else:
        version = latest_changelog_version()
        if not version:
            print('ERROR: no version in the manual and none found in changelog.html.',
                  file=sys.stderr)
            sys.exit(1)
        print(f'Note: the manual declares no version; using {version} '
              f'from changelog.html.')

    # Everything between the H1 and the first horizontal rule.
    intro_match = re.search(r'^# .+?\n+(.*?)^---', raw, re.DOTALL | re.MULTILINE)
    intro_text = ''
    if intro_match:
        body = re.sub(r'^_For version .+?_\s*', '', intro_match.group(1).strip())
        intro_text = ' '.join(body.split())
    if not intro_text:
        print('WARNING: the intro paragraph came out empty.', file=sys.stderr)

    sections_raw = [s for s in re.split(r'^(?=## )', raw, flags=re.MULTILINE)
                    if s.startswith('## ')]
    content_html = '\n'.join(process_section(s) for s in sections_raw)

    guide_content = (
        f'  <!-- ── CONTENT ── -->\n'
        f'  <div class="guide-content">\n\n'
        f'    <div class="page-header">\n'
        f'      <h1>User Guide</h1>\n'
        f'      <p class="version">For version {escape(version)}</p>\n'
        f'      <p class="intro">{inline(escape(intro_text))}</p>\n'
        f'    </div>\n'
        f'{content_html}\n\n'
        f'  </div><!-- /.guide-content -->'
    )

    # Fix email address in Credits to be a mailto link
    guide_content = guide_content.replace(
        '<strong>support@greylineft8.com</strong>',
        '<a href="mailto:support@greylineft8.com">support@greylineft8.com</a>'
    )

    with open(HTML_TARGET, 'r') as f:
        html = f.read()

    pattern = r'  <!-- ── CONTENT ── -->.*?</div><!-- /\.guide-content -->'

    if not re.search(pattern, html, flags=re.DOTALL):
        print('ERROR: content marker not found in HTML — nothing was changed.', file=sys.stderr)
        sys.exit(1)

    result = re.sub(pattern, guide_content, html, flags=re.DOTALL)

    with open(HTML_TARGET, 'w') as f:
        f.write(result)

    changed = result != html
    print(f'Done. Synced {len(sections_raw)} sections from {MD_SOURCE}'
          + ('' if changed else ' (no changes)'))

    problems, notes = check_links(result)
    if problems:
        print(f'\nWARNING: {len(problems)} broken link(s) — '
              f'the table of contents is hand-maintained and needs fixing by hand:',
              file=sys.stderr)
        for p in problems:
            print(f'  - {p}', file=sys.stderr)
    if notes:
        print(f'\nFYI: {len(notes)} wording difference(s), harmless if deliberate:',
              file=sys.stderr)
        for n in notes:
            print(f'  - {n}', file=sys.stderr)


if __name__ == '__main__':
    main()
