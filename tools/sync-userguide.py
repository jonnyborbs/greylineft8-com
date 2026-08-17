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


def escape(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


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
    Continuation lines are any non-blank lines that don't start a new block."""
    text = lines[start][2:].strip()  # strip leading '- '
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
        text += ' ' + line.strip()
        i += 1
    return text, i


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
            out.append(f'{indent}<h4>{inline(escape(line[5:].strip()))}</h4>')
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
                out.append(f'{indent}  <li>{inline(escape(item_text))}</li>')
            out.append(f'{indent}</ul>')
            continue

        # Ordered list
        if re.match(r'^\d+\. ', line):
            out.append(f'{indent}<ol>')
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                item_text = re.sub(r'^\d+\. ', '', lines[i]).strip()
                i += 1
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
        h3_slug = slugify(h3_title)
        out.append(f'      <h3 id="{h3_slug}"><a href="#{h3_slug}">'
                   f'{inline(escape(h3_title))}</a></h3>')
        if i + 1 < len(subsections):
            out.extend(parse_block(subsections[i + 1].strip().split('\n')))
        i += 2

    out.append('    </section>')
    return '\n'.join(out)


def main():
    with open(MD_SOURCE, 'r') as f:
        raw = f.read()

    version_match = re.search(r'^_For version (.+?)_', raw, re.MULTILINE)
    version = version_match.group(1) if version_match else '1.2'

    intro_match = re.search(r'^_For version .+?_\n\n(.*?)^---', raw, re.DOTALL | re.MULTILINE)
    intro_text = intro_match.group(1).strip().replace('\n', ' ') if intro_match else ''

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


if __name__ == '__main__':
    main()
