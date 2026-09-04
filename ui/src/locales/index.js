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

// Keep upstream API/resource names unchanged, but present infrastructure in
// customer language. CloudStack's backend Zone and Pod objects remain untouched;
// only their customer-facing labels are translated to Site and Infrastructure
// group. The zone wizard separately calls the Pod networking step Management
// network because that is what the customer is configuring there.
const layersentryEnglishTerminology = {
  'message.layersentry.kvm.select.site': 'Select a Site to check KVM availability.',
  'message.layersentry.kvm.checking': 'Checking KVM availability for the selected Site…',
  'message.layersentry.kvm.unavailable': 'The selected Site does not report KVM capability. Choose another Site or ask your administrator to configure KVM.',
  'message.layersentry.kvm.lookup.failed': 'KVM availability could not be verified. Check your connection and permissions, then select the Site again.',
  'message.layersentry.kvm.image.invalid': 'The selected OS image cannot be verified for KVM in this Site. Select a ready KVM image or a compatible bootable ISO. Snapshot sources must have a readable KVM volume.',
  'message.layersentry.kvm.image.lookup.failed': 'The selected image could not be checked. Check your connection and permissions, then retry.',
  'message.layersentry.kvm.selection.changed': 'The Site or image selection changed during validation. Review your selection and submit again.',
  'label.zone': 'Site',
  'label.zones': 'Sites',
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

  'label.core.zone.type': 'Network design',
  'label.core': 'Datacenter site',
  'label.edge': 'Edge site',
  'label.advanced': 'Advanced networking',
  'label.basic': 'Simple shared networking',
  'label.menu.security.groups': 'VM firewall groups',

  'label.network': 'Networks',
  'label.physical.network': 'Datacenter network',
  'label.public.traffic': 'Public / Internet network',
  'label.guest.traffic': 'VM / Workload network',
  'label.storage.traffic': 'Storage network',
  'label.management.network': 'Management network',

  'label.pod': 'Infrastructure group',
  'label.pods': 'Infrastructure groups',
  'label.podid': 'Infrastructure group',
  'label.podname': 'Infrastructure group name',
  'label.pod.name': 'Infrastructure group name',
  'label.pod.dedicated': 'Dedicated infrastructure group',
  'label.action.delete.pod': 'Delete infrastructure group',
  'label.action.disable.pod': 'Disable infrastructure group',
  'label.action.enable.pod': 'Enable infrastructure group',
  'label.action.update.pod': 'Update infrastructure group',
  'label.podstorageaccessgroups': 'Infrastructure group storage access groups',

  'label.reserved.system.gateway': 'Management network gateway',
  'label.reserved.system.netmask': 'Management network subnet mask',
  'label.start.reserved.system.ip': 'Management IP range start',
  'label.end.reserved.system.ip': 'Management IP range end',

  'label.add.resources': 'Compute & storage',
  'label.launch': 'Review & create',
  'label.register.template': 'OS image',

  'message.desc.core.zone': 'Use this for a normal datacenter or private-cloud site. It supports the full infrastructure model including compute clusters, hypervisor hosts, shared storage, isolated workload networks and high availability.',
  'message.desc.edge.zone': 'Use this for a small remote or branch location with a reduced infrastructure footprint. Choose this only when you intentionally need an edge deployment.',
  'message.desc.advanced.zone': 'Recommended for enterprise and private-cloud deployments. Supports isolated VM networks, VLANs, VPC-style networking, firewall, VPN and load-balancing services.',
  'message.desc.basic.zone': 'A simpler shared-network model where workloads use addresses directly from the same network. Choose this only for small or uncomplicated environments.',
  'message.advanced.security.group': 'Optional VM-level source-IP filtering. Leave this off when you plan to use isolated networks and network-level firewall policies.',
  'message.add.pod.during.zone.creation': 'Create the first infrastructure group and define its management network. An infrastructure group is a set of compute clusters and hypervisor hosts that share the same management subnet. For a small single-cluster deployment, one infrastructure group is normally enough.',
  'message.installwizard.tooltip.addpod.name': 'Enter a friendly group name, for example rack-01 or management-group-01.',
  'message.installwizard.tooltip.addpod.reservedsystemgateway': 'Enter the gateway for the management subnet.',
  'message.tooltip.reserved.system.netmask': 'Enter the subnet mask for the management network.',
  'message.installwizard.tooltip.addpod.reservedsystemstartip': 'Enter the first IP address in the management IP pool reserved for platform system services.',
  'message.installwizard.tooltip.addpod.reservedsystemendip': 'Enter the last IP address in the management IP pool reserved for platform system services.',
  'message.network.description': 'Configure the networks used for platform management, virtual-machine workloads, storage and optional public access.',
  'message.network.hint': 'Use separate VLANs or subnets for management, workloads and storage when your network design supports it.',
  'message.add.resource.description': 'Add the compute cluster, virtualization hosts and storage that will run this site.',
  'message.launch.zone.description': 'Review the configuration before creating the site.',
  'message.zone.detail.description': 'Name the site and configure the basic platform and DNS settings for this location.'
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
