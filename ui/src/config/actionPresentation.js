// Presentation-only action semantics. CloudStack action objects, API names,
// permission checks, visibility predicates and click payloads remain unchanged.
const ACTION_ICON_RULES = [
  [/^(create|add|register|upload|deploy)/i, 'plus-outlined'],
  [/^(delete|destroy|remove|expunge|revoke)/i, 'delete-outlined'],
  [/^(start|enable|activate)/i, 'play-circle-outlined'],
  [/^(stop|disable|suspend)/i, 'pause-circle-outlined'],
  [/^(restart|reboot|reset)/i, 'reload-outlined'],
  [/^(update|edit|rename|change)/i, 'edit-outlined'],
  [/^(migrate|move|scale)/i, 'swap-outlined'],
  [/^(attach|associate|assign)/i, 'paper-clip-outlined'],
  [/^(detach|disassociate|unassign)/i, 'disconnect-outlined'],
  [/^(recover|restore|revert)/i, 'history-outlined'],
  [/^(copy|clone)/i, 'copy-outlined'],
  [/^(download|export)/i, 'download-outlined']
]

export function resolveActionIcon (action = {}) {
  if (typeof action.icon !== 'string' || typeof action.api !== 'string') {
    return action.icon
  }
  const match = ACTION_ICON_RULES.find(([pattern]) => pattern.test(action.api))
  return match ? match[1] : action.icon
}

export function isDestructiveAction (action = {}) {
  return /^(delete|destroy|remove|expunge|revoke)/i.test(action.api || '')
}
