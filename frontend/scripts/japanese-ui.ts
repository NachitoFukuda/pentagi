import type { Plugin } from 'vite';

import ts from 'typescript';

import messages from '../src/locales/ja.json' with { type: 'json' };

const technicalFields = new Set([
    'action',
    'className',
    'code',
    'data-testid',
    'displayName',
    'download',
    'href',
    'id',
    'key',
    'method',
    'name',
    'path',
    'role',
    'size',
    'src',
    'status',
    'to',
    'type',
    'value',
    'variant',
]);
const dictionary: Readonly<Record<string, string>> = messages;

export function japaneseUi(enabled = true): Plugin {
    return {
        enforce: 'pre',
        name: 'pentagi-japanese-ui',
        transform(source, id) {
            const filename = id.split('?')[0] ?? id;

            if (
                !enabled ||
                !filename.includes('/src/') ||
                !/\.[jt]sx?$/.test(filename) ||
                filename.includes('/node_modules/') ||
                /\/graphql\/|\.test\.|\.spec\./.test(filename)
            ) {
                return;
            }

            const code = localizeJapaneseUi(source, filename);

            if (code !== source) {
                return { code, map: null };
            }
        },
        transformIndexHtml(html) {
            return html.replace(/\blang="(?:en|ja)"/, `lang="${enabled ? 'ja' : 'en'}"`);
        },
    };
}

/** Localize reviewed, static UI copy before React compiles it. No DOM rewriting, network calls,
 * or translation of server responses, user documents, terminal output, or API identifiers. */
export function localizeJapaneseUi(source: string, filename: string, translations = dictionary): string {
    const file = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true);
    const edits: { end: number; start: number; text: string }[] = [];
    const translate = (value: string) => (Object.hasOwn(translations, value) ? translations[value] : undefined);

    const protectedLiteral = (node: ts.Node): boolean => {
        for (let parent = node.parent; parent; parent = parent.parent) {
            if (
                ts.isTypeNode(parent) ||
                ts.isImportDeclaration(parent) ||
                ts.isExportDeclaration(parent) ||
                ts.isEnumDeclaration(parent) ||
                (ts.isCaseClause(parent) && parent.expression === node)
            ) {
                return true;
            }

            if (
                ts.isBinaryExpression(parent) &&
                [
                    ts.SyntaxKind.EqualsEqualsEqualsToken,
                    ts.SyntaxKind.EqualsEqualsToken,
                    ts.SyntaxKind.ExclamationEqualsEqualsToken,
                    ts.SyntaxKind.ExclamationEqualsToken,
                ].includes(parent.operatorToken.kind)
            ) {
                return true;
            }

            if (ts.isJsxAttribute(parent)) {
                return technicalFields.has(parent.name.getText(file));
            }

            if (ts.isPropertyAssignment(parent)) {
                if (parent.name === node) {
                    return true;
                }

                return technicalFields.has(parent.name.getText(file).replace(/^['"]|['"]$/g, ''));
            }

            if (ts.isElementAccessExpression(parent)) {
                return true;
            }

            if (ts.isStatement(parent) || ts.isJsxExpression(parent)) {
                break;
            }
        }

        return false;
    };

    const displayFields =
        /^(label|title|description|message|placeholder|text|header|tooltip|headline|detail|actionLabel|fallback|emptyTitle|emptyDescription|searchPlaceholder|confirmText|buttonText|submitText|cancelText|entityName)$/i;

    const displayContext = (node: ts.Node): boolean => {
        for (let parent = node.parent; parent; parent = parent.parent) {
            if (ts.isJsxExpression(parent) || ts.isJsxAttribute(parent)) {
                return true;
            }

            if (ts.isPropertyAssignment(parent)) {
                return displayFields.test(parent.name.getText(file).replace(/^['"]|['"]$/g, ''));
            }

            if (ts.isCallExpression(parent)) {
                const callee = parent.expression.getText(file);

                if (
                    /^(toast|notify)(\.|$)/.test(callee) ||
                    /\.(min|max|email|refine|regex|nonempty|length)$/.test(callee)
                ) {
                    return true;
                }
            }

            if (ts.isNewExpression(parent) && parent.expression.getText(file) === 'Error') {
                return true;
            }

            if (ts.isVariableDeclaration(parent)) {
                return /(?:label|title|description|message|placeholder|tooltip|text|instruction|heading)/i.test(
                    parent.name.getText(file),
                );
            }

            if (ts.isFunctionDeclaration(parent)) {
                return /(?:format|validate|error|message|label|title)/i.test(parent.name?.text ?? '');
            }

            if (ts.isStatement(parent) && !ts.isReturnStatement(parent)) {
                break;
            }
        }

        return false;
    };

    function visit(node: ts.Node) {
        if (protectedLiteral(node)) {
            return;
        }

        if (ts.isJsxText(node)) {
            const normalized = node.text.replace(/\s+/g, ' ').trim();
            const translated = translate(normalized);

            if (translated !== undefined) {
                // JSX text whitespace has special semantics. Keep its boundary whitespace; escape
                // the replacement as a JS expression so braces, ampersands and quotes stay literal.
                const leading = node.text.match(/^\s*/)?.[0] ?? '';
                const trailing = node.text.match(/\s*$/)?.[0] ?? '';
                edits.push({
                    end: node.end,
                    start: node.pos,
                    text: `${leading}{${JSON.stringify(translated)}}${trailing}`,
                });
            }

            return;
        }

        if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
            if (!displayContext(node)) {
                return;
            }

            // Lowercase one-word tokens are often wire values. Only translate them in JSX
            // text or a field explicitly intended for display.
            if (
                /^[a-z]+$/.test(node.text) &&
                !(
                    ts.isPropertyAssignment(node.parent) &&
                    /^(label|title|description|message|placeholder|text|entityName)$/.test(
                        node.parent.name.getText(file),
                    )
                )
            ) {
                return;
            }

            const translated = translate(node.text);

            if (translated !== undefined) {
                edits.push({ end: node.end, start: node.getStart(file), text: JSON.stringify(translated) });
            }

            return;
        }

        if (ts.isTemplateExpression(node) && displayContext(node)) {
            const key =
                node.head.text + node.templateSpans.map((span, index) => `{${index}}${span.literal.text}`).join('');
            const translated = translate(key);

            if (translated !== undefined) {
                const parts: string[] = [];
                let offset = 0;

                for (const match of translated.matchAll(/\{(\d+)\}/g)) {
                    const span = node.templateSpans[Number(match[1])];

                    if (!span) {
                        throw new Error(`Invalid translation placeholder: ${key}`);
                    }

                    parts.push(
                        JSON.stringify(translated.slice(offset, match.index)),
                        `(${span.expression.getText(file)})`,
                    );
                    offset = match.index + match[0].length;
                }

                parts.push(JSON.stringify(translated.slice(offset)));
                edits.push({ end: node.end, start: node.getStart(file), text: `(${parts.join(' + ')})` });

                return;
            }
        }

        ts.forEachChild(node, visit);
    }

    visit(file);

    return edits
        .sort((a, b) => b.start - a.start)
        .reduce((text, edit) => text.slice(0, edit.start) + edit.text + text.slice(edit.end), source);
}
