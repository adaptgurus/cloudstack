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

import { createI18n } from 'vue-i18n'
import { vueProps } from '@/vue-app'

const loadedLanguage = []
const messages = {}

// Keep upstream API/resource names unchanged, but present LayerSentry's KVM
// infrastructure in customer language. CloudStack's backend resource model is
// untouched. Ambiguous concepts such as Cluster are not globally renamed.
export const layersentryEnglishTerminology = {
  'label.layersentry.quick.provision': 'Quick Provision',
  'label.layersentry.platform-admin': 'Platform Administrator',
  'label.layersentry.department-admin': 'Department Administrator',
  'label.layersentry.user': 'User / Operator',
  'label.layersentry.read-only': 'Read-only / Auditor',
  'label.layersentry.project': 'Project',
  'label.layersentry.platform.operations': 'LayerSentry Platform Operations',
  'label.layersentry.self.service': 'LayerSentry Self Service',
  'label.layersentry.all.sites': 'All Sites',
  'label.layersentry.kvm.hosts': 'KVM Hosts',
  'label.layersentry.compute.clusters': 'Compute Clusters',
  'label.layersentry.infrastructure.groups': 'Infrastructure Groups',
  'label.layersentry.storage.pools': 'Storage Pools',
  'label.layersentry.platform.services': 'Platform Services',
  'label.layersentry.protection.services': 'Protection & Services',
  'label.layersentry.capacity': 'Capacity',
  'label.layersentry.recent.alerts': 'Recent Alerts',
  'label.layersentry.recent.activity': 'Recent Activity',
  'label.layersentry.attention.required': 'Attention required',
  'label.layersentry.host.exceptions': 'host state exception(s)',
  'label.layersentry.offerings.available': 'offering(s) available',
  'label.layersentry.not.configured': 'Not configured',
  'label.layersentry.available': 'Available',
  'label.layersentry.unavailable': 'Unavailable',
  'label.layersentry.optional.services': 'Optional services',
  'label.layersentry.no.capacity': 'No capacity records were returned for this scope.',
  'label.layersentry.no.alerts': 'No current alerts were returned.',
  'label.layersentry.no.events': 'No recent activity was returned.',
  'label.layersentry.partial.data': 'Some dashboard data could not be loaded: {sections}.',
  'message.layersentry.platform.dashboard': 'KVM infrastructure health, capacity, service readiness and recent exceptions reported by CloudStack.',
  'message.layersentry.platform.dashboard.failed': 'The Platform Dashboard could not be loaded. Check CloudStack API access and retry.',
  'message.layersentry.backup.dashboard.fact': 'Backup availability is shown from configured CloudStack backup offerings; this does not claim that every VM is protected.',
  'message.layersentry.bucket.dashboard.fact': 'Bucket count is shown only when the CloudStack bucket API is granted to this role.',
  'message.layersentry.optional.services.unavailable': 'No optional service inventory API is currently available to this role.',
  'message.layersentry.kvm.select.site': 'Select a Site to check KVM availability.',
  'message.layersentry.kvm.checking': 'Checking KVM availability for the selected Site…',
  'message.layersentry.kvm.unavailable': 'The selected Site does not report KVM capability. Choose another Site or ask your administrator to configure KVM.',
  'message.layersentry.kvm.lookup.failed': 'KVM availability could not be verified. Check your connection and permissions, then select the Site again.',
  'message.layersentry.kvm.image.invalid': 'The selected OS Image cannot be verified for KVM in this Site. Select a ready KVM OS Image or a compatible bootable ISO. Snapshot sources must have a readable KVM volume.',
  'message.layersentry.kvm.image.lookup.failed': 'The selected OS Image could not be checked. Check your connection and permissions, then retry.',
  'message.layersentry.kvm.selection.changed': 'The Site or OS Image selection changed during validation. Review your selection and submit again.',

  // CloudStack Zone -> LayerSentry Site.
  'label.zone': 'Site',
  'label.zones': 'Sites',
  'label.all.zone': 'All Sites',
  'label.select.a.zone': 'Select a Site',
  'label.select.zones': 'Select Sites',
  'label.destination.zone': 'Destination Site',
  'label.zone.id': 'Site ID',
  'label.zoneid': 'Site',
  'label.zonename': 'Site',
  'label.zonenamelabel': 'Site name',
  'label.zone.dedicated': 'Dedicated site',
  'label.zone.wide': 'Site-wide',
  'label.zone.type': 'Site type',
  'label.zone.details': 'Site details',
  'label.action.delete.zone': 'Delete site',
  'label.action.disable.zone': 'Disable site',
  'label.action.enable.zone': 'Enable site',
  'label.action.edit.zone': 'Edit site',
  'label.action.update.zone': 'Update site',

  // CloudStack Pod -> LayerSentry Infrastructure Group.
  'label.pod': 'Infrastructure Group',
  'label.pods': 'Infrastructure Groups',
  'label.podid': 'Infrastructure Group',
  'label.podname': 'Infrastructure Group name',
  'label.pod.name': 'Infrastructure Group name',
  'label.pod.dedicated': 'Dedicated Infrastructure Group',
  'label.destination.pod': 'Destination Infrastructure Group',
  'label.action.delete.pod': 'Delete Infrastructure Group',
  'label.action.disable.pod': 'Disable Infrastructure Group',
  'label.action.enable.pod': 'Enable Infrastructure Group',
  'label.action.update.pod': 'Update Infrastructure Group',
  'label.podstorageaccessgroups': 'Infrastructure Group storage access groups',

  // CloudStack Domain is the LayerSentry Department tenancy boundary.
  'label.domain': 'Department',
  'label.domains': 'Departments',
  'label.domain.id': 'Department ID',
  'label.domain.name': 'Department name',
  'label.domainid': 'Department',
  'label.domainname': 'Department',
  'label.domainpath': 'Department',

  // KVM-only host presentation.
  'label.host': 'KVM Host',
  'label.hosts': 'KVM Hosts',

  // CloudStack Service Offering -> LayerSentry Compute Profile.
  'label.compute.offerings': 'Compute Profiles',
  'label.service.offering': 'Compute Profile',
  'label.serviceofferingid': 'Compute Profile',
  'label.serviceofferingname': 'Compute Profile',

  // CloudStack Disk Offering -> VM Storage Profile.
  'label.disk.offerings': 'Storage Profiles',
  'label.diskoffering': 'Storage Profile',
  'label.diskofferingdisplaytext': 'Storage Profile',
  'label.diskofferingid': 'Storage Profile',
  'label.data.disk.offering': 'Data Storage Profile',

  // CloudStack VM Template -> LayerSentry OS Image. Email/quota templates use
  // separate keys and are therefore unaffected.
  'label.template': 'OS Image',
  'label.templates': 'OS Images',
  'label.template.select': 'Select an OS Image',
  'label.template.select.existing': 'Select an existing OS Image',
  'label.templateid': 'Select an OS Image',
  'label.templatename': 'OS Image',
  'label.templateiso': 'OS Image / ISO',
  'label.create.template': 'Create OS Image',
  'label.register.template': 'Register OS Image',
  'label.upload.template.from.local': 'Upload OS Image from local file',
  'label.confirm.delete.templates': 'Please confirm you wish to delete the selected OS Images.',
  'label.deleting.template': 'Deleting OS Image',

  'label.core.zone.type': 'Network design',
  'label.core': 'Datacenter site',
  'label.edge': 'Edge site',
  'label.advanced': 'Advanced networking',
  'label.basic': 'Simple shared networking',
  'label.menu.security.groups': 'VM firewall groups',

  'label.network': 'Networks',
  'label.guest.networks': 'Workload Networks',
  'label.physical.network': 'Datacenter network',
  'label.public.traffic': 'Public / Internet network',
  'label.guest.traffic': 'VM / Workload network',
  'label.storage.traffic': 'Storage network',
  'label.management.network': 'Management network',

  'label.reserved.system.gateway': 'Management network gateway',
  'label.reserved.system.netmask': 'Management network subnet mask',
  'label.start.reserved.system.ip': 'Management IP range start',
  'label.end.reserved.system.ip': 'Management IP range end',

  'label.add.resources': 'Compute & storage',
  'label.launch': 'Review & create',

  'message.desc.core.zone': 'Use this for a normal datacenter or private-cloud site. It supports the full infrastructure model including compute clusters, KVM hosts, shared storage, isolated workload networks and high availability.',
  'message.desc.edge.zone': 'Use this for a small remote or branch location with a reduced infrastructure footprint. Choose this only when you intentionally need an edge deployment.',
  'message.desc.advanced.zone': 'Recommended for enterprise and private-cloud deployments. Supports isolated VM networks, VLANs, VPC-style networking, firewall, VPN and load-balancing services.',
  'message.desc.basic.zone': 'A simpler shared-network model where workloads use addresses directly from the same network. Choose this only for small or uncomplicated environments.',
  'message.advanced.security.group': 'Optional VM-level source-IP filtering. Leave this off when you plan to use isolated networks and network-level firewall policies.',
  'message.add.pod.during.zone.creation': 'Create the first Infrastructure Group and define its management network. An Infrastructure Group is a set of Compute Clusters and KVM Hosts that share the same management subnet. For a small single-cluster deployment, one Infrastructure Group is normally enough.',
  'message.installwizard.tooltip.addpod.name': 'Enter a friendly group name, for example rack-01 or management-group-01.',
  'message.installwizard.tooltip.addpod.reservedsystemgateway': 'Enter the gateway for the management subnet.',
  'message.tooltip.reserved.system.netmask': 'Enter the subnet mask for the management network.',
  'message.installwizard.tooltip.addpod.reservedsystemstartip': 'Enter the first IP address in the management IP pool reserved for platform system services.',
  'message.installwizard.tooltip.addpod.reservedsystemendip': 'Enter the last IP address in the management IP pool reserved for platform system services.',
  'message.network.description': 'Configure the networks used for platform management, virtual-machine workloads, storage and optional public access.',
  'message.network.hint': 'Use separate VLANs or subnets for management, workloads and storage when your network design supports it.',
  'message.add.resource.description': 'Add the Compute Cluster, KVM Hosts and storage that will run this Site.',
  'message.launch.zone.description': 'Review the configuration before creating the Site.',
  'message.zone.detail.description': 'Name the Site and configure the basic platform and DNS settings for this location.'
}

export const i18n = createI18n({
  locale: 'en',
  fallbackLocale: 'en',
  silentTranslationWarn: true,
  messages: messages,
  silentFallbackWarn: true,
  warnHtmlInMessage: 'off'
})

export function loadLanguageAsync (lang) {
  if (!lang) {
    const locale = vueProps.$localStorage.get('LOCALE')
    lang = (!locale || typeof locale === 'object') ? 'en' : locale
  }
  if (loadedLanguage.includes(lang)) {
    return Promise.resolve(setLanguage(lang))
  }

  return fetch(`locales/${lang}.json?ts=${Date.now()}`)
    .then(response => response.json())
    .then(json => Promise.resolve(setLanguage(lang, json)))
}

function setLanguage (lang, message) {
  if (i18n) {
    i18n.global.locale = lang

    if (message && Object.keys(message).length > 0) {
      i18n.global.setLocaleMessage(lang, message)
    }

    if (lang === 'en') {
      i18n.global.mergeLocaleMessage(lang, layersentryEnglishTerminology)
    }
  }

  if (!loadedLanguage.includes(lang)) {
    loadedLanguage.push(lang)
  }

  if (message && Object.keys(message).length > 0) {
    messages[lang] = message
  }
}
