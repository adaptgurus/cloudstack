// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied. See the License for the
// specific language governing permissions and limitations
// under the License.

import {
  getLayersentryFeatureState,
  hasApi,
  isLayersentryFeatureVisible,
  LAYERSENTRY_FEATURES
} from '@/config/layersentryCapabilities'

const profile = {
  productProfile: 'layersentry-kvm'
}

describe('LayerSentry GUI capability gates', () => {
  it('enables Quick Provision only when the native deploy API is granted', () => {
    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.QUICK_PROVISION,
      { deployVirtualMachine: {} },
      profile
    )).toBe(true)

    const missing = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.QUICK_PROVISION,
      { listVirtualMachines: {} },
      profile
    )
    expect(missing.visible).toBe(false)
    expect(missing.reason).toBe('missing-api')
    expect(missing.missingApis).toEqual(['deployVirtualMachine'])
  })

  it('does not expose LayerSentry-only GUI features outside the LayerSentry profile', () => {
    const state = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.QUICK_PROVISION,
      { deployVirtualMachine: {} },
      { productProfile: 'upstream' }
    )
    expect(state.visible).toBe(false)
    expect(state.reason).toBe('product-profile')
  })

  it('keeps provider-backed GUI routes hidden until policy marks them ready', () => {
    const disabled = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.BACKUP,
      { listBackupOfferings: {} },
      profile
    )
    expect(disabled.visible).toBe(false)
    expect(disabled.reason).toBe('disabled')

    const notReady = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.BACKUP,
      { listBackupOfferings: {} },
      {
        ...profile,
        layersentry: { features: { backup: { enabled: true } } }
      }
    )
    expect(notReady.visible).toBe(false)
    expect(notReady.reason).toBe('not-ready')
  })

  it('requires both provider readiness and the prerequisite API', () => {
    const config = {
      ...profile,
      layersentry: {
        features: {
          backup: { enabled: true, ready: true },
          buckets: { enabled: true, ready: true }
        }
      }
    }

    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.BACKUP,
      { listBackupOfferings: {} },
      config
    )).toBe(true)
    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.BACKUP,
      {},
      config
    )).toBe(false)
    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.BUCKETS,
      { listBuckets: {} },
      config
    )).toBe(true)
  })

  it('applies provider policy when LayerSentry dashboard code asks whether a gated API is usable', () => {
    const apis = {
      listBackupOfferings: {},
      listBuckets: {},
      listVirtualMachines: {}
    }
    expect(hasApi(apis, 'listBackupOfferings', profile)).toBe(false)
    expect(hasApi(apis, 'listBuckets', profile)).toBe(false)
    expect(hasApi(apis, 'listVirtualMachines', profile)).toBe(true)

    const ready = {
      ...profile,
      layersentry: {
        features: {
          backup: { enabled: true, ready: true },
          buckets: { enabled: true, ready: true }
        }
      }
    }
    expect(hasApi(apis, 'listBackupOfferings', ready)).toBe(true)
    expect(hasApi(apis, 'listBuckets', ready)).toBe(true)
  })

  it('does not apply LayerSentry provider policy to upstream profiles', () => {
    expect(hasApi(
      { listBackupOfferings: {} },
      'listBackupOfferings',
      { productProfile: 'upstream' }
    )).toBe(true)
  })

  it('treats non-GUI product modules as unknown in this workstream', () => {
    const state = getLayersentryFeatureState('externalModule', {}, profile)
    expect(state.visible).toBe(false)
    expect(state.reason).toBe('unknown-feature')
  })
})
