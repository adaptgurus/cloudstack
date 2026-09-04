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

// Keep upstream API/resource names unchanged, but present infrastructure setup
// in terms customers can understand. In particular, the backend "pod" object is
// shown as an Infrastructure Group and its reserved-system fields are described
// as the management network/IP pool they configure.
const layersentryEnglishTerminology = {
  'label.zone.type': 'Site type',
  'label.core.zone.type': 'Network design',
  'label.zone.details': 'Site details',
  'label.network': 'Networks',
  'label.add.resources': 'Compute & storage',
  'label.launch': 'Review & create',
  'label.register.template': 'OS image',
  'label.core': 'Datacenter site',
  'label.edge': 'Edge site',
  'label.advanced': 'Advanced networking',
  'label.basic': 'Simple shared networking',
  'label.menu.security.groups': 'VM firewall groups',
  'label.physical.network': 'Datacenter network',
  'label.public.traffic': 'Public / Internet network',
  'label.guest.traffic': 'VM / Workload network',
  'label.storage.traffic': 'Storage network',
  'label.pod': 'Management network',
  'label.pod.name': 'Infrastructure group name',
  'label.reserved.system.gateway': 'Management network gateway',
  'label.reserved.system.netmask': 'Management network subnet mask',
  'label.start.reserved.system.ip': 'Management IP range start',
  'label.end.reserved.system.ip': 'Management IP range end',
  'message.desc.core.zone': 'Use this for a normal datacenter or private-cloud site. It supports the full infrastructure model including clusters, hosts, shared storage, isolated workload networks and high availability.',
  'message.desc.edge.zone': 'Use this for a small remote or branch location with a reduced infrastructure footprint. Choose this only when you intentionally need an edge deployment.',
  'message.desc.advanced.zone': 'Recommended for enterprise and private-cloud deployments. Supports isolated VM networks, VLANs, VPC-style networking, firewall, VPN and load-balancing services.',
  'message.desc.basic.zone': 'A simpler shared-network model where workloads use addresses directly from the same network. Choose this only for small or uncomplicated environments.',
  'message.advanced.security.group': 'Optional VM-level source-IP filtering. Leave this off when you plan to use isolated networks and network-level firewall policies.',
  'message.add.pod.during.zone.creation': 'Create the first infrastructure group and define its management network. An infrastructure group is a set of clusters and hosts that share the same management subnet. For a small single-cluster deployment, one group is normally enough.',
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
