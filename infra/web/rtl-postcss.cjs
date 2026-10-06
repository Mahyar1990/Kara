const postcssRTLCSS = require('postcss-rtlcss')
const selectorParser = require('postcss-selector-parser')

// :dir() follows the element's effective direction, including LTR code/canvas islands.
// :where() avoids changing Tailwind utility specificity.
const directionSelector = (prefix, selector) => {
  const direction = prefix.includes('rtl') ? 'rtl' : 'ltr'
  return selectorParser((root) => {
    root.each((item) => {
      const pseudo = selectorParser.pseudo({ value: `:where(:dir(${direction}))` })
      const elementPseudo = item.nodes.find(node => node.type === 'pseudo'
        && (node.value.startsWith('::') || [':before', ':after'].includes(node.value)))
      if (elementPseudo) item.insertBefore(elementPseudo, pseudo)
      else item.append(pseudo)
    })
  }).processSync(selector)
}

const createPlugin = () => postcssRTLCSS({
  mode: 'combined',
  safeBothPrefix: true,
  runOnExit: true,
  processDeclarationPlugins: [{
    name: 'tailwind-horizontal-translation',
    priority: 99,
    processors: [{
      expr: /^--tw-translate-x$/,
      action: (prop, value) => ({ prop, value: `calc(${value} * -1)` }),
    }],
  }],
  prefixSelectorTransformer: (prefix, selector) =>
    prefix === '[dir]' ? selector : directionSelector(prefix, selector),
})

createPlugin.postcss = true
module.exports = createPlugin
module.exports.directionSelector = directionSelector
