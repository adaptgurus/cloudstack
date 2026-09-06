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

import { vueProps } from '@/vue-app'
import { isLayersentryKvmProfile } from './productProfile'

// GUI-only capability gates. Kubernetes, DBaaS, APaaS and streaming belong to
// separate workstreams and are intentionally not represented here.
export const LAYERSENTRY_FEATURES = Object.freeze({
  QUICK_PROVISION: 'quickProvision',
  BUCKETS: 'buckets',
  BACKUP: 'backup',
  DR: 'dr'
})

const FEATURE_DEFINITIONS = Object.freeze({
  [LAYERSENTRY_FEATURES.QUICK_PROVISION]: {
    defaultEnabled: true,
    requiredApis: ['deployVirtualMachine'],
    requireReady: false
  },
  [LAYERSENTRY_FEATURES.BUCKETS]: {
    defaultEnabled: false,
    requiredApis: ['listBuckets'],
    requireReady: true
  },
  [LAYERSENTRY_FEATURES.BACKUP]: {
    defaultEnabled: false,
    requiredApis: ['listBackupOfferings'],
    requireReady: true
  },
  [LAYERSENTRY_FEATURES.DR]: {
    defaultEnabled: false,
    requiredApis: [],
    requireReady: true
  }
})

const FEATURE_API_MAP = Object.freeze({
  listBuckets: LAYERSENTRY_FEATURES.BUCKETS,
  createBucket: LAYERSENTRY_FEATURES.BUCKETS,
  updateBucket: LAYERSENTRY_FEATURES.BUCKETS,
  deleteBucket: LAYERSENTRY_FEATURES.BUCKETS,
  listBackupOfferings: LAYERSENTRY_FEATURES.BACKUP,
  listBackups: LAYERSENTRY_FEATURES.BACKUP,
  listBackupSchedule: LAYERSENTRY_FEATURES.BACKUP,
  createBackup: LAYERSENTRY_FEATURES.BACKUP,
  createBackupSchedule: LAYERSENTRY_FEATURES.BACKUP,
  restoreBackup: LAYERSENTRY_FEATURES.BACKUP,
  assignVirtualMachineToBackupOffering: LAYERSENTRY_FEATURES.BACKUP
})

function rawHasApi (apis = {}, api) {
  return Boolean(api) && Object.prototype.hasOwnProperty.call(apis || {}, api)
}

export function hasApi (apis = {}, api, config = vueProps.$config) {
  if (!rawHasApi(apis, api)) return false
  const gatedFeature = FEATURE_API_MAP[api]
  if (!gatedFeature || !isLayersentryKvmProfile(config)) return true
  return getLayersentryFeatureState(gatedFeature, apis, config).visible
}

export function hasAllApis (apis = {}, requiredApis = []) {
  return requiredApis.every(api => rawHasApi(apis, api))
}

function normalisePolicy (config, feature, definition) {
  const raw = config?.layersentry?.features?.[feature]
  if (typeof raw === 'boolean') {
    return { enabled: raw }
  }
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw
  }
  return { enabled: definition.defaultEnabled }
}

export function getLayersentryFeatureState (feature, apis = {}, config = vueProps.$config) {
  const definition = FEATURE_DEFINITIONS[feature]
  if (!definition) {
    return {
      feature,
      visible: false,
      enabled: false,
      ready: false,
      reason: 'unknown-feature',
      missingApis: []
    }
  }

  if (!isLayersentryKvmProfile(config)) {
    return {
      feature,
      visible: false,
      enabled: false,
      ready: false,
      reason: 'product-profile',
      missingApis: []
    }
  }

  const policy = normalisePolicy(config, feature, definition)
  const enabled = policy.enabled !== undefined ? Boolean(policy.enabled) : definition.defaultEnabled
  if (!enabled) {
    return {
      feature,
      visible: false,
      enabled: false,
      ready: false,
      reason: 'disabled',
      missingApis: []
    }
  }

  const ready = definition.requireReady ? policy.ready === true : policy.ready !== false
  if (!ready) {
    return {
      feature,
      visible: false,
      enabled: true,
      ready: false,
      reason: 'not-ready',
      missingApis: []
    }
  }

  const requiredApis = Array.isArray(policy.requiredApis)
    ? policy.requiredApis
    : definition.requiredApis
  const missingApis = requiredApis.filter(api => !rawHasApi(apis, api))
  if (missingApis.length > 0) {
    return {
      feature,
      visible: false,
      enabled: true,
      ready: true,
      reason: 'missing-api',
      missingApis
    }
  }

  return {
    feature,
    visible: true,
    enabled: true,
    ready: true,
    reason: 'ready',
    missingApis: []
  }
}

export function getLayersentryCapabilities (apis = {}, config = vueProps.$config) {
  return Object.values(LAYERSENTRY_FEATURES).reduce((states, feature) => {
    states[feature] = getLayersentryFeatureState(feature, apis, config)
    return states
  }, {})
}

export function isLayersentryFeatureVisible (feature, apis = {}, config = vueProps.$config) {
  return getLayersentryFeatureState(feature, apis, config).visible
}
