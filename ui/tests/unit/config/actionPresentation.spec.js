import { isDestructiveAction, resolveActionIcon } from '@/config/actionPresentation'

describe('LayerSentry action presentation', () => {
  it.each([
    ['deployVirtualMachine', 'plus-outlined'],
    ['startVirtualMachine', 'play-circle-outlined'],
    ['stopVirtualMachine', 'pause-circle-outlined'],
    ['rebootVirtualMachine', 'reload-outlined'],
    ['updateVirtualMachine', 'edit-outlined'],
    ['migrateVirtualMachine', 'swap-outlined'],
    ['attachVolume', 'paper-clip-outlined'],
    ['detachVolume', 'disconnect-outlined'],
    ['recoverVirtualMachine', 'history-outlined'],
    ['destroyVirtualMachine', 'delete-outlined']
  ])('maps %s to a semantic icon', (api, icon) => {
    expect(resolveActionIcon({ api, icon: 'question-outlined' })).toBe(icon)
  })

  it('preserves custom and non-string icons', () => {
    const custom = { api: 'runCustomAction', icon: 'thunderbolt-outlined' }
    const objectIcon = { prefix: 'fas', iconName: 'server' }
    expect(resolveActionIcon(custom)).toBe(custom.icon)
    expect(resolveActionIcon({ api: 'startThing', icon: objectIcon })).toBe(objectIcon)
  })

  it('does not mutate or filter the action object', () => {
    const action = { api: 'deleteNetwork', icon: 'close-outlined', show: () => true }
    expect(resolveActionIcon(action)).toBe('delete-outlined')
    expect(action).toEqual(expect.objectContaining({
      api: 'deleteNetwork',
      icon: 'close-outlined',
      show: expect.any(Function)
    }))
  })

  it('marks only destructive API verbs as destructive', () => {
    expect(isDestructiveAction({ api: 'deleteVolume' })).toBe(true)
    expect(isDestructiveAction({ api: 'destroyVirtualMachine' })).toBe(true)
    expect(isDestructiveAction({ api: 'detachVolume' })).toBe(false)
    expect(isDestructiveAction({ api: 'updateVolume' })).toBe(false)
  })
})
