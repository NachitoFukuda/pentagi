// @vitest-environment node
import ts from 'typescript';
import { describe, expect, it } from 'vitest';

import { japaneseUi, localizeJapaneseUi } from '../../scripts/japanese-ui';
import messages from '../../src/locales/ja.json';

const localize = (source: string) => localizeJapaneseUi(source, '/app/src/view.tsx');

describe('Japanese UI build', () => {
    it('translates React text, attributes, conditional copy, and notifications', () => {
        const result = localize(
            `const view = <><h1>Account</h1><input placeholder="Search..." /><button>{busy ? 'Loading...' : 'Save'}</button></>; toast.success('Copied to clipboard');`,
        );
        expect(result).toContain('{"アカウント"}');
        expect(result).toContain('placeholder="検索…"');
        expect(result).toContain('busy ? "読み込み中…" : "保存"');
        expect(result).toContain('toast.success("クリップボードにコピーしました")');
        expect(
            ts.transpileModule(result, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX }, reportDiagnostics: true })
                .diagnostics,
        ).toEqual([]);
    });

    it('keeps API values, form bindings, CSS, imports, enum declarations, and comparisons unchanged', () => {
        const source = `import { Account } from 'Account'; type State = 'Running'; enum S { Running = 'Running' }; const protocol = 'Account'; const request = { status: 'Running', name: 'Name', type: 'Text', value: 'Account' }; const view = <input name="Name" value={'Account'} className="Text" />; if (value === 'Running') send(request);`;
        expect(localize(source)).toBe(source);
    });

    it('changes display labels while preserving wire values in the same object', () => {
        expect(localize(`const option = { label: 'Running', value: 'Running' };`)).toBe(
            `const option = { label: "実行中", value: 'Running' };`,
        );
        expect(localize(`const option = { label: 'active', value: 'active' };`)).toBe(
            `const option = { label: "有効", value: 'active' };`,
        );
    });

    it('reorders interpolation placeholders and preserves expressions as data', () => {
        const result = localize(
            'const message = `An item named "${name}" already exists at /${path}. Do you want to replace it?`;',
        );
        expect(result).toContain('(path)');
        expect(result).toContain('(name)');
        expect(result.indexOf('(path)')).toBeLessThan(result.indexOf('(name)'));
        expect(result).toContain('置き換えますか？');
    });

    it('localizes switch result labels without changing case identifiers', () => {
        expect(
            localize(
                `function view(state: string) { switch (state) { case 'Running': return <span>Running</span>; } }`,
            ),
        ).toContain(`case 'Running': return <span>{"実行中"}</span>`);
    });

    it('leaves dynamic document and terminal content untouched', () => {
        expect(
            localize(
                'const view = <><Markdown>{document.text}</Markdown><Terminal value={log.output} /><input value={user.name} /></>;',
            ),
        ).toBe(
            'const view = <><Markdown>{document.text}</Markdown><Terminal value={log.output} /><input value={user.name} /></>;',
        );
    });

    it('keeps every translation interpolation and rejects missing interpolation references', () => {
        for (const [key, value] of Object.entries(messages)) {
            expect([...value.matchAll(/\{\d+\}/g)].map(([part]) => part).sort(), key).toEqual(
                [...key.matchAll(/\{\d+\}/g)].map(([part]) => part).sort(),
            );
        }

        expect(() => localizeJapaneseUi('const title = `Hello ${name}`;', 'x.ts', { 'Hello {0}': '{1}' })).toThrow(
            'Invalid translation placeholder',
        );
    });

    it('supports an English build and excludes generated GraphQL modules', async () => {
        const off = japaneseUi(false);
        const transform = off.transform as (this: unknown, source: string, id: string) => unknown;
        expect(await transform.call({}, 'const title = "Account";', '/app/src/view.tsx')).toBeUndefined();
        const on = japaneseUi();
        expect(
            await (on.transform as typeof transform).call({}, 'const title = "Account";', '/app/src/graphql/types.ts'),
        ).toBeUndefined();
    });
});
