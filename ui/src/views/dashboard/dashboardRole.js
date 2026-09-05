// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

const SELF_SERVICE_MUTATIONS = [
  'deployVirtualMachine',
  'createVolume',
  'createNetwork',
  'createKubernetesCluster',
  'createBucket',
  'registerTemplate',
  'createProject'
]

function hasApi (apis, api) {
  return Object.prototype.hasOwnProperty.call(apis || {}, api)
}

export function getDashboardRole (userInfo = {}, apis = {}, showProject = false) {
  if (showProject) {
    return 'project'
  }
  if (!SELF_SERVICE_MUTATIONS.some(api => hasApi(apis, api))) {
    return 'read-only'
  }
  if (userInfo.roletype === 'DomainAdmin') {
    return 'department-admin'
  }
  return 'user'
}

export function getDashboardQuickActions (apis = {}) {
  const actions = []
  if (hasApi(apis, 'deployVirtualMachine')) {
    actions.push({ key: 'instance', label: 'label.vm.add', path: '/action/deployVirtualMachine' })
  }
  return actions
}
