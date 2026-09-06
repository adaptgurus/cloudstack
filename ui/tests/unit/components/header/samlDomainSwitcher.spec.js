import SamlDomainSwitcher from '@/components/header/SamlDomainSwitcher.vue'
import Cookies from 'js-cookie'
import { postAPI } from '@/api'
import store from '@/store'

jest.mock('@/api', () => ({ postAPI: jest.fn() }))
jest.mock('@/store', () => ({ getters: { userInfo: { id: 'user-a' } }, dispatch: jest.fn() }))
jest.mock('js-cookie', () => ({ get: jest.fn() }))

const flush = () => new Promise(resolve => setTimeout(resolve, 0))

describe('SAML account discovery', () => {
  beforeEach(() => jest.clearAllMocks())
  it('does not query SAML accounts during password login', () => {
    Cookies.get.mockReturnValue('false')
    const vm = { showSwitcher: true, loading: true }
    SamlDomainSwitcher.methods.fetchData.call(vm)
    expect(postAPI).not.toHaveBeenCalled()
    expect(vm).toEqual({ showSwitcher: false, loading: false })
  })
  it('preserves SAML account discovery and clears loading for a single account', async () => {
    Cookies.get.mockReturnValue('true')
    postAPI.mockResolvedValue({ listandswitchsamlaccountresponse: { count: 1, samluseraccount: [{ userId: 'user-a' }] } })
    const vm = { showSwitcher: false, loading: false }
    SamlDomainSwitcher.methods.fetchData.call(vm)
    await flush()
    expect(postAPI).toHaveBeenCalledWith('listAndSwitchSamlAccount', expect.objectContaining({ page: 1 }))
    expect(vm.loading).toBe(false)
    expect(vm.showSwitcher).toBe(false)
  })
  it('waits for later pages before resolving the current SAML account', async () => {
    Cookies.get.mockReturnValue('true')
    postAPI.mockResolvedValueOnce({
      listandswitchsamlaccountresponse: {
        count: 3,
        samluseraccount: [
          { userId: 'user-b', domainPath: '/b' }, { userId: 'user-c', domainPath: '/c' }
        ]
      }
    }).mockResolvedValueOnce({
      listandswitchsamlaccountresponse: {
        count: 3,
        samluseraccount: [
          { userId: 'user-a', accountName: 'Team A', domainName: 'A', domainPath: '/a' }
        ]
      }
    })
    const vm = { showSwitcher: false, loading: false }
    await SamlDomainSwitcher.methods.fetchData.call(vm)
    expect(postAPI).toHaveBeenCalledTimes(2)
    expect(vm.currentAccount).toBe('Team A (A)')
    expect(vm.showSwitcher).toBe(true)
    expect(vm.loading).toBe(false)
  })
  it('reports refresh failure after account switching without reloading', async () => {
    postAPI.mockResolvedValue({})
    store.dispatch.mockRejectedValue(new Error('permission discovery failed'))
    const vm = { samlAccounts: [{ userId: 'user-a', domainId: 'domain-a' }], $message: { error: jest.fn(), success: jest.fn() }, $router: { go: jest.fn() }, $t: key => key }
    await SamlDomainSwitcher.methods.changeAccount.call(vm, 0)
    expect(vm.$message.error).toHaveBeenCalledWith('message.error.discovering.feature')
    expect(vm.$message.success).not.toHaveBeenCalled()
    expect(vm.$router.go).not.toHaveBeenCalled()
  })
})
