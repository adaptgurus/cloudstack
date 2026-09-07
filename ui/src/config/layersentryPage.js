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

// LayerSentry presentation metadata; routes, API names and actions stay native.
const groups = [
  ['vm vmgroup affinitygroup ssh userdata', 'compute', 'Manage virtual machines, placement and access in the current authorized scope.'],
  ['volume diskoffering sharedfs', 'storage', 'Review capacity, attachment and Storage Profiles before changing workload storage.'],
  ['snapshot snapshotpolicy vmsnapshot', 'recovery', 'Manage snapshot recovery points and schedules. Snapshots are distinct from VM backups.'],
  ['backup backupschedule backupoffering backuprepository', 'backup', 'Review provider-backed backups and recovery operations. Protection requires a confirmed provider result.'],
  ['guestnetwork vpc acllist privategw ilb publicip securitygroups networkoffering vpcoffering', 'network', 'Manage workload connectivity and the services supplied by each Network Blueprint.'],
  ['s2svpn s2svpnconn vpnuser vpncustomergateway', 'connectivity', 'Review endpoint configuration and reported connection state.'],
  ['template iso kubernetesiso computeoffering systemoffering', 'images', 'Choose compatible images and profiles for the intended workload.'],
  ['zone zones pod cluster host infrasummary systemvm router ilbvm managementserver storagepool imagestore objectstore', 'infrastructure', 'Inspect Sites, compute, storage and platform services. Inventory alone does not establish readiness.'],
  ['domain account accountuser project role user', 'identity', 'Manage authorized teams, projects and access. Users within one Account share its resource ownership.'],
  ['event alert webhookdeliveries', 'activity', 'Review reported events, alerts and delivery results in the current authorized scope.'],
  ['usage quotasummary quotatariff quotaemailtemplate', 'consumption', 'Review reported consumption and configured quota policy.'],
  ['buckets', 'objects', 'Manage buckets through the configured Object Store and its permitted operations.'],
  ['kubernetes', 'kubernetes', 'Manage native Kubernetes clusters and inspect their reported lifecycle state.'],
  ['globalsetting ldapsetting oauthsetting extension customaction webhook comment', 'administration', 'Review configuration and integration impact before applying an authorized change.']
]

export function layersentryPage (routeName) {
  const group = groups.find(([routes]) => routes.split(' ').includes(routeName))
  return group ? { section: group[1], description: group[2] } : {
    section: 'platform', description: 'Inspect resources and use the actions available to your role in the current scope.'
  }
}

export function readFailure (error) {
  const response = error?.response
  const envelope = response?.data
  const payload = envelope && typeof envelope === 'object'
    ? Object.entries(envelope).find(([key, value]) => key.endsWith('response') && value && typeof value === 'object')?.[1]
    : null
  const text = value => typeof value === 'string' || typeof value === 'number' ? String(value).slice(0, 2000) : ''
  return {
    status: [401, 403, 405].includes(response?.status) ? 'forbidden' : 'error',
    code: text(payload?.errorcode || response?.status),
    message: text(payload?.errortext || response?.headers?.['x-description'] || error?.message),
    requestId: text(response?.headers?.['x-request-id'] || payload?.uuid)
  }
}
