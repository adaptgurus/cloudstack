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
import { getLayersentryFeatureState, hasApi, LAYERSENTRY_FEATURES } from './layersentryCapabilities'
import { isLayersentryKvmProfile } from './productProfile'

const KVM_SCOPED_ROUTES = new Set(['vm', 'host', 'cluster', 'template'])

const USER_HIDDEN_SECTIONS = new Set([
  'user',
  'account',
  'domain',
  'role',
  'infra',
  'zone',
  'offering',
  'config',
  'extension',
  'customaction'
])

const DOMAIN_ADMIN_HIDDEN_SECTIONS = new Set([
  'role',
  'infra',
  'zone',
  'offering',
  'config',
  'extension',
  'customaction'
])

// Only GUI/provider surfaces owned by Workstream A are gated here. Native
// CloudStack Kubernetes and data-service products are intentionally untouched.
const FEATURE_ROUTES = Object.freeze({
  backup: LAYERSENTRY_FEATURES.BACKUP,
  backupschedule: LAYERSENTRY_FEATURES.BACKUP,
  backupoffering: LAYERSENTRY_FEATURES.BACKUP,
  buckets: LAYERSENTRY_FEATURES.BUCKETS
})

export function withLayersentryKvmParams (routeName, params, config = vueProps.$config) {
  if (!isLayersentryKvmProfile(config) || !KVM_SCOPED_ROUTES.has(routeName)) {
    return params
  }

  if (typeof params === 'function') {
    return (...args) => ({
      ...(params(...args) || {}),
      hypervisor: 'KVM'
    })
  }

  return {
    ...(params || {}),
    hypervisor: 'KVM'
  }
}

export function shouldHideLayersentrySection (sectionName, userInfo = {}, config = vueProps.$config) {
  if (!isLayersentryKvmProfile(config)) return false
  if (userInfo.roletype === 'Admin') return false
  if (userInfo.roletype === 'DomainAdmin') return DOMAIN_ADMIN_HIDDEN_SECTIONS.has(sectionName)
  return USER_HIDDEN_SECTIONS.has(sectionName)
}

export function shouldHideLayersentryFeatureRoute (routeName, apis = {}, config = vueProps.$config) {
  if (!isLayersentryKvmProfile(config)) return false
  const backupReadApi = { backup: 'listBackups', backupschedule: 'listBackupSchedule', backupoffering: 'listBackupOfferings' }[routeName]
  if (backupReadApi) return !hasApi(apis, backupReadApi, config)
  const feature = FEATURE_ROUTES[routeName]
  if (!feature) return false
  return !getLayersentryFeatureState(feature, apis, config).visible
}

function applyFeatureRouteVisibility (route, apis, config) {
  if (!route) return route
  const children = Array.isArray(route.children)
    ? route.children.map(child => applyFeatureRouteVisibility(child, apis, config))
    : route.children
  const normalized = children === route.children ? route : { ...route, children }
  if (!route.name || !shouldHideLayersentryFeatureRoute(route.name, apis, config)) {
    return normalized
  }
  return {
    ...normalized,
    hidden: true
  }
}

export function applyLayersentryNavigation (routes = [], userInfo = {}, config = vueProps.$config, apis = {}) {
  if (!isLayersentryKvmProfile(config)) return routes
  return routes.map(originalRoute => {
    let route = applyFeatureRouteVisibility(originalRoute, apis, config)
    if (!route || !route.name) return route
    if (!shouldHideLayersentrySection(route.name, userInfo, config)) return route
    route = {
      ...route,
      hidden: true
    }
    return route
  })
}
