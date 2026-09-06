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
  isLayersentryFeatureVisible,
  LAYERSENTRY_FEATURES
} from '@/config/layersentryCapabilities'

const profile = {
  productProfile: 'layersentry-kvm'
}

describe('LayerSentry capability gates', () => {
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

  it('does not expose LayerSentry-only features outside the LayerSentry product profile', () => {
    const state = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.QUICK_PROVISION,
      { deployVirtualMachine: {} },
      { productProfile: 'upstream' }
    )
    expect(state.visible).toBe(false)
    expect(state.reason).toBe('product-profile')
  })

  it('keeps managed modules hidden until policy marks the real backend ready', () => {
    const disabled = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.DBAAS,
      {},
      profile
    )
    expect(disabled.visible).toBe(false)
    expect(disabled.reason).toBe('disabled')

    const notReady = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.DBAAS,
      {},
      {
        ...profile,
        layersentry: { features: { dbaas: { enabled: true } } }
      }
    )
    expect(notReady.visible).toBe(false)
    expect(notReady.reason).toBe('not-ready')
  })

  it('supports explicit backend API requirements for managed modules', () => {
    const config = {
      ...profile,
      layersentry: {
        features: {
          managedKubernetes: {
            enabled: true,
            ready: true,
            requiredApis: ['listLayerSentryClusters', 'createLayerSentryCluster']
          }
        }
      }
    }

    const missing = getLayersentryFeatureState(
      LAYERSENTRY_FEATURES.MANAGED_KUBERNETES,
      { listLayerSentryClusters: {} },
      config
    )
    expect(missing.visible).toBe(false)
    expect(missing.reason).toBe('missing-api')
    expect(missing.missingApis).toEqual(['createLayerSentryCluster'])

    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.MANAGED_KUBERNETES,
      {
        listLayerSentryClusters: {},
        createLayerSentryCluster: {}
      },
      config
    )).toBe(true)
  })

  it('supports the native CKS inventory only when CloudStack exposes it', () => {
    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.NATIVE_KUBERNETES,
      { listKubernetesClusters: {} },
      profile
    )).toBe(true)
    expect(isLayersentryFeatureVisible(
      LAYERSENTRY_FEATURES.NATIVE_KUBERNETES,
      {},
      profile
    )).toBe(false)
  })
})
