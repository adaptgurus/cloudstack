import SamlDomainSwitcher from '@/components/header/SamlDomainSwitcher.vue'
import Cookies from 'js-cookie'
import { postAPI } from '@/api'

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
})
