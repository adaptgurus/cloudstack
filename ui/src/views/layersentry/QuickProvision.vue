<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements. See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership. The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License. You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing,
 software distributed under the License is distributed on an
 "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 KIND, either express or implied. See the License for the
 specific language governing permissions and limitations
 under the License.
-->

<template>
  <div class="ls-quick-provision">
    <div class="ls-quick-hero">
      <div>
        <div class="ls-eyebrow">LAYERSENTRY PRIVATE CLOUD</div>
        <h1>Quick Provision</h1>
        <p>
          Provision a KVM virtual machine from one page. LayerSentry resolves the
          selected Site, compute, storage and workload-network policy while
          CloudStack remains authoritative for placement and lifecycle.
        </p>
      </div>
      <div class="ls-hero-tags">
        <a-tag color="green">KVM only</a-tag>
        <a-tag>Native CloudStack orchestration</a-tag>
      </div>
    </div>

    <a-alert
      v-if="loadError"
      type="error"
      show-icon
      :message="loadError"
      class="ls-alert" />

    <a-row :gutter="16">
      <a-col :xs="24" :xl="17">
        <a-form layout="vertical" :model="form" @finish="deploy">
          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><environment-outlined /> Ownership &amp; Site</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="VM name" name="name" :rules="[{ required: true, message: 'Enter a VM name' }]">
                  <a-input v-model:value="form.name" placeholder="app-prod-01" autocomplete="off" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Site" name="zoneid" :rules="[{ required: true, message: 'Select a Site' }]">
                  <a-select
                    v-model:value="form.zoneid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.zones"
                    :options="zoneOptions"
                    placeholder="Select Site"
                    @change="onZoneChange" />
                </a-form-item>
              </a-col>
            </a-row>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><cloud-server-outlined /> Compute</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="OS Image" name="templateid" :rules="[{ required: true, message: 'Select an OS Image' }]">
                  <a-select
                    v-model:value="form.templateid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.templates"
                    :options="templateOptions"
                    :disabled="!form.zoneid"
                    placeholder="Select KVM OS Image" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Compute Profile" name="serviceofferingid" :rules="[{ required: true, message: 'Select a Compute Profile' }]">
                  <a-select
                    v-model:value="form.serviceofferingid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.compute"
                    :options="computeOptions"
                    :disabled="!form.zoneid"
                    placeholder="Select Compute Profile" />
                </a-form-item>
              </a-col>
            </a-row>
            <div class="ls-inline-state">
              <a-tag color="green">KVM</a-tag>
              <span>Other upstream hypervisors are intentionally not exposed by the LayerSentry customer profile.</span>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><database-outlined /> Storage</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="Additional Storage Profile (optional)">
                  <a-select
                    v-model:value="form.diskofferingid"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.storage"
                    :options="storageOptions"
                    :disabled="!form.zoneid"
                    placeholder="No additional data volume" />
                </a-form-item>
              </a-col>
              <a-col v-if="selectedStorageProfile && selectedStorageProfile.iscustomized" :xs="24" :md="12">
                <a-form-item label="Data volume size (GiB)" name="size" :rules="customDiskRules">
                  <a-input-number v-model:value="form.size" :min="1" :precision="0" style="width: 100%" />
                </a-form-item>
              </a-col>
            </a-row>
            <div class="ls-callout">
              <database-outlined />
              <div>
                <strong>Storage backend is policy-driven.</strong>
                <span>
                  NFS, iSCSI/FC SAN, Ceph, LINSTOR and other certified backends are presented as Storage Profiles.
                  Tenant users never receive SAN target credentials or raw LUN controls.
                </span>
              </div>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><apartment-outlined /> Network</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="VPC (optional)">
                  <a-select
                    v-model:value="form.vpcid"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.vpcs"
                    :options="vpcOptions"
                    :disabled="!form.zoneid || !canListVpcs"
                    placeholder="Site networks / no VPC"
                    @change="loadNetworks" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item
                  label="Network Blueprint"
                  name="networkid"
                  :rules="networkRules">
                  <a-select
                    v-model:value="form.networkid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.networks"
                    :options="networkOptions"
                    :disabled="!form.zoneid || selectedZoneNetworkType === 'Basic'"
                    :placeholder="selectedZoneNetworkType === 'Basic' ? 'Managed by the Site' : 'Select workload network'" />
                </a-form-item>
              </a-col>
              <a-col v-if="canOverrideIp && selectedZoneNetworkType !== 'Basic'" :xs="24" :md="12">
                <a-form-item label="Private IP override (optional)">
                  <a-input v-model:value.trim="form.ipaddress" placeholder="Automatic from destination pool" autocomplete="off" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-descriptions v-if="selectedNetwork" size="small" :column="networkDescriptionColumns" bordered>
              <a-descriptions-item label="Resolved network">{{ selectedNetwork.name }}</a-descriptions-item>
              <a-descriptions-item label="VLAN policy">{{ resolvedVlan }}</a-descriptions-item>
              <a-descriptions-item label="CIDR">{{ selectedNetwork.cidr || 'Provider managed' }}</a-descriptions-item>
              <a-descriptions-item label="Gateway">{{ selectedNetwork.gateway || 'Provider managed' }}</a-descriptions-item>
              <a-descriptions-item label="DNS">{{ resolvedDns }}</a-descriptions-item>
              <a-descriptions-item label="Network domain">{{ selectedNetwork.networkdomain || 'Site policy' }}</a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><safety-certificate-outlined /> Availability &amp; Protection</span>
            </template>
            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <div class="ls-feature-row">
                  <div>
                    <strong>VM HA</strong>
                    <div class="ls-muted">Derived from the selected Compute Profile and Site prerequisites.</div>
                  </div>
                  <a-tag :color="selectedComputeProfile && selectedComputeProfile.offerha ? 'green' : 'default'">
                    {{ selectedComputeProfile && selectedComputeProfile.offerha ? 'Enabled by profile' : 'Not enabled by profile' }}
                  </a-tag>
                </div>
              </a-col>
              <a-col :xs="24" :md="12">
                <div class="ls-feature-row">
                  <div>
                    <strong>Backup &amp; DR</strong>
                    <div class="ls-muted">Protection is enabled only when a real provider, Site Pair and policy are available.</div>
                  </div>
                  <a-tag color="orange">Capability gated</a-tag>
                </div>
              </a-col>
            </a-row>
            <a-alert
              type="info"
              show-icon
              message="Quick Provision will never mark a VM Protected or DR Ready until the protection controller confirms the post-deploy operation." />
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><check-circle-outlined /> Review &amp; Deploy</span>
            </template>
            <a-checkbox v-model:checked="form.startvm">Start VM after provisioning</a-checkbox>
            <div class="ls-actions">
              <a-button @click="$router.back()">Cancel</a-button>
              <a-button type="primary" html-type="submit" :loading="deploying" :disabled="!readyToDeploy">
                <rocket-outlined /> Provision VM
              </a-button>
            </div>
          </a-card>
        </a-form>
      </a-col>

      <a-col :xs="24" :xl="7">
        <a-affix :offset-top="76">
          <a-card class="ls-plan-card" :bordered="false" title="Resolved plan">
            <div class="ls-plan-row"><span>Site</span><strong>{{ selectedZone?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Hypervisor</span><strong>KVM</strong></div>
            <div class="ls-plan-row"><span>OS Image</span><strong>{{ selectedTemplate?.displaytext || selectedTemplate?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Compute</span><strong>{{ selectedComputeProfile?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Data storage</span><strong>{{ selectedStorageProfile?.displaytext || selectedStorageProfile?.name || 'None' }}</strong></div>
            <div class="ls-plan-row"><span>VPC</span><strong>{{ selectedVpc?.name || 'None' }}</strong></div>
            <div class="ls-plan-row"><span>Network</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : (selectedNetwork?.name || 'Not selected') }}</strong></div>
            <div class="ls-plan-row"><span>Private IP</span><strong>{{ form.ipaddress || 'Automatic' }}</strong></div>
            <div class="ls-plan-row"><span>VLAN</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : resolvedVlan }}</strong></div>
            <a-divider />
            <div class="ls-preflight">
              <check-circle-outlined v-if="readyToDeploy" class="ls-ok" />
              <info-circle-outlined v-else />
              <span>{{ readyToDeploy ? 'Core provisioning inputs are resolved.' : 'Complete the required fields to run preflight.' }}</span>
            </div>
          </a-card>
        </a-affix>
      </a-col>
    </a-row>
  </div>
</template>

<script>
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  EnvironmentOutlined,
  InfoCircleOutlined,
  RocketOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons-vue'
import { getAPI, postAPI } from '@/api'

export default {
  name: 'LayersentryQuickProvision',
  components: {
    ApartmentOutlined,
    CheckCircleOutlined,
    CloudServerOutlined,
    DatabaseOutlined,
    EnvironmentOutlined,
    InfoCircleOutlined,
    RocketOutlined,
    SafetyCertificateOutlined
  },
  data () {
    return {
      form: {
        name: '',
        zoneid: undefined,
        templateid: undefined,
        serviceofferingid: undefined,
        diskofferingid: undefined,
        size: undefined,
        vpcid: undefined,
        networkid: undefined,
        ipaddress: '',
        startvm: true
      },
      zones: [],
      templates: [],
      computeProfiles: [],
      storageProfiles: [],
      vpcs: [],
      networks: [],
      loading: {
        zones: false,
        templates: false,
        compute: false,
        storage: false,
        vpcs: false,
        networks: false
      },
      deploying: false,
      loadError: ''
    }
  },
  computed: {
    canListVpcs () {
      return Boolean(this.$store.getters.apis?.listVPCs)
    },
    canOverrideIp () {
      return ['Admin', 'DomainAdmin'].includes(this.$store.getters.userInfo?.roletype)
    },
    selectedZone () {
      return this.zones.find(item => item.id === this.form.zoneid)
    },
    selectedZoneNetworkType () {
      return this.selectedZone?.networktype || ''
    },
    selectedTemplate () {
      return this.templates.find(item => item.id === this.form.templateid)
    },
    selectedComputeProfile () {
      return this.computeProfiles.find(item => item.id === this.form.serviceofferingid)
    },
    selectedStorageProfile () {
      return this.storageProfiles.find(item => item.id === this.form.diskofferingid)
    },
    selectedVpc () {
      return this.vpcs.find(item => item.id === this.form.vpcid)
    },
    selectedNetwork () {
      return this.networks.find(item => item.id === this.form.networkid)
    },
    zoneOptions () {
      return this.zones.map(item => ({ label: item.name, value: item.id }))
    },
    templateOptions () {
      return this.templates.map(item => ({
        label: item.displaytext || item.name,
        value: item.id
      }))
    },
    computeOptions () {
      return this.computeProfiles.map(item => ({
        label: item.displaytext || item.name,
        value: item.id
      }))
    },
    storageOptions () {
      return this.storageProfiles.map(item => ({
        label: item.displaytext || item.name,
        value: item.id
      }))
    },
    vpcOptions () {
      return this.vpcs.map(item => ({ label: item.displaytext || item.name, value: item.id }))
    },
    networkOptions () {
      return this.networks.map(item => ({
        label: item.displaytext || item.name,
        value: item.id
      }))
    },
    resolvedVlan () {
      if (!this.selectedNetwork) return 'Automatic'
      if (!['Admin'].includes(this.$store.getters.userInfo?.roletype)) return 'Automatic by Network Blueprint'
      const raw = this.selectedNetwork.vlan || this.selectedNetwork.broadcasturi
      if (!raw) return 'Automatic by Network Blueprint'
      return String(raw).replace(/^vlan:\/\//i, '')
    },
    resolvedDns () {
      if (!this.selectedNetwork) return 'Site policy'
      return [this.selectedNetwork.dns1, this.selectedNetwork.dns2]
        .filter(Boolean)
        .join(', ') || 'Site policy'
    },
    networkRules () {
      if (!this.form.zoneid || this.selectedZoneNetworkType === 'Basic') return []
      return [{ required: true, message: 'Select a Network Blueprint' }]
    },
    customDiskRules () {
      if (!this.selectedStorageProfile?.iscustomized) return []
      return [{ required: true, type: 'number', min: 1, message: 'Enter a data volume size' }]
    },
    readyToDeploy () {
      const core = this.form.name && this.form.zoneid && this.form.templateid && this.form.serviceofferingid
      if (!core) return false
      if (this.selectedZoneNetworkType !== 'Basic' && !this.form.networkid) return false
      if (this.selectedStorageProfile?.iscustomized && !this.form.size) return false
      return true
    },
    networkDescriptionColumns () {
      return window.innerWidth < 900 ? 1 : 2
    }
  },
  mounted () {
    this.loadZones()
  },
  methods: {
    responseItems (response, responseKey, itemKey) {
      return response?.[responseKey]?.[itemKey] || []
    },
    selectOnlyOption (field, items) {
      if (items.length === 1) this.form[field] = items[0].id
    },
    async loadZones () {
      this.loading.zones = true
      this.loadError = ''
      try {
        const response = await getAPI('listZones', { showicon: true })
        this.zones = this.responseItems(response, 'listzonesresponse', 'zone')
        if (this.zones.length === 1) {
          this.form.zoneid = this.zones[0].id
          await this.onZoneChange(this.form.zoneid)
        }
      } catch (error) {
        this.loadError = 'Unable to load Sites. Check CloudStack API access and try again.'
        console.error(error)
      } finally {
        this.loading.zones = false
      }
    },
    resetZoneDependencies () {
      this.form.templateid = undefined
      this.form.serviceofferingid = undefined
      this.form.diskofferingid = undefined
      this.form.size = undefined
      this.form.vpcid = undefined
      this.form.networkid = undefined
      this.form.ipaddress = ''
      this.templates = []
      this.computeProfiles = []
      this.storageProfiles = []
      this.vpcs = []
      this.networks = []
    },
    async onZoneChange () {
      this.resetZoneDependencies()
      if (!this.form.zoneid) return
      await Promise.all([
        this.loadTemplates(),
        this.loadComputeProfiles(),
        this.loadStorageProfiles(),
        this.loadVpcs()
      ])
      await this.loadNetworks()
    },
    async loadTemplates () {
      this.loading.templates = true
      try {
        const response = await getAPI('listTemplates', {
          templatefilter: 'executable',
          zoneid: this.form.zoneid,
          isready: true,
          listall: true,
          showicon: true,
          details: 'all'
        })
        const templates = this.responseItems(response, 'listtemplatesresponse', 'template')
        this.templates = templates.filter(item => item.hypervisor === 'KVM')
        this.selectOnlyOption('templateid', this.templates)
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.templates = false
      }
    },
    async loadComputeProfiles () {
      this.loading.compute = true
      try {
        const response = await getAPI('listServiceOfferings', {
          zoneid: this.form.zoneid,
          issystem: false,
          listall: true
        })
        this.computeProfiles = this.responseItems(response, 'listserviceofferingsresponse', 'serviceoffering')
        this.selectOnlyOption('serviceofferingid', this.computeProfiles)
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.compute = false
      }
    },
    async loadStorageProfiles () {
      this.loading.storage = true
      try {
        const response = await getAPI('listDiskOfferings', {
          zoneid: this.form.zoneid,
          listall: true
        })
        this.storageProfiles = this.responseItems(response, 'listdiskofferingsresponse', 'diskoffering')
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.storage = false
      }
    },
    async loadVpcs () {
      this.vpcs = []
      if (!this.canListVpcs) return
      this.loading.vpcs = true
      try {
        const response = await getAPI('listVPCs', {
          zoneid: this.form.zoneid,
          listall: true
        })
        this.vpcs = this.responseItems(response, 'listvpcsresponse', 'vpc')
      } catch (error) {
        console.warn('VPC inventory is not available for this role.', error)
      } finally {
        this.loading.vpcs = false
      }
    },
    async loadNetworks () {
      this.form.networkid = undefined
      this.form.ipaddress = ''
      this.networks = []
      if (!this.form.zoneid || this.selectedZoneNetworkType === 'Basic') return
      this.loading.networks = true
      try {
        const params = {
          zoneid: this.form.zoneid,
          canusefordeploy: true,
          listall: true,
          showicon: true
        }
        if (this.form.vpcid) params.vpcid = this.form.vpcid
        const response = await getAPI('listNetworks', params)
        this.networks = this.responseItems(response, 'listnetworksresponse', 'network')
        this.selectOnlyOption('networkid', this.networks)
      } catch (error) {
        this.$notifyError(error)
      } finally {
        this.loading.networks = false
      }
    },
    buildDeployParams () {
      const params = {
        name: this.form.name,
        displayname: this.form.name,
        zoneid: this.form.zoneid,
        templateid: this.form.templateid,
        serviceofferingid: this.form.serviceofferingid,
        hypervisor: 'KVM',
        startvm: this.form.startvm
      }

      if (this.form.diskofferingid) {
        params.diskofferingid = this.form.diskofferingid
        if (this.selectedStorageProfile?.iscustomized && this.form.size) params.size = this.form.size
      }

      if (this.selectedZoneNetworkType !== 'Basic' && this.form.networkid) {
        params['iptonetworklist[0].networkid'] = this.form.networkid
        if (this.form.ipaddress) params['iptonetworklist[0].ip'] = this.form.ipaddress
      }

      return params
    },
    async deploy () {
      if (!this.readyToDeploy || this.deploying) return
      this.deploying = true
      try {
        const response = await postAPI('deployVirtualMachine', this.buildDeployParams())
        const jobId = response?.deployvirtualmachineresponse?.jobid
        if (!jobId) throw new Error('CloudStack did not return an async job ID.')

        this.$pollJob({
          jobId,
          title: 'Quick Provision',
          description: this.form.name,
          loadingMessage: `Provisioning ${this.form.name}`,
          catchMessage: this.$t('error.fetching.async.job.result'),
          successMethod: result => {
            const vm = result?.jobresult?.virtualmachine
            const vmName = vm?.displayname || vm?.name || this.form.name
            this.$notification.success({
              message: 'Virtual machine provisioned',
              description: `${vmName} was created through the native CloudStack KVM workflow.`
            })
            this.deploying = false
            if (vm?.id) this.$router.push({ path: `/vm/${vm.id}` })
          },
          action: { isFetchData: false }
        })
      } catch (error) {
        this.$notifyError(error)
        this.deploying = false
      }
    }
  }
}
</script>

<style scoped>
.ls-quick-provision {
  max-width: 1500px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.ls-quick-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding: 8px 4px 22px;
}

.ls-quick-hero h1 {
  margin: 2px 0 8px;
  font-size: 30px;
  line-height: 1.2;
}

.ls-quick-hero p {
  max-width: 820px;
  margin: 0;
  color: rgba(0, 0, 0, 0.56);
  font-size: 15px;
  line-height: 1.65;
}

.ls-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  opacity: 0.58;
}

.ls-hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.ls-alert,
.ls-section-card {
  margin-bottom: 16px;
}

.ls-section-card,
.ls-plan-card {
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 10px 26px rgba(0, 0, 0, 0.03);
}

.ls-section-title {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-weight: 650;
}

.ls-inline-state {
  display: flex;
  gap: 9px;
  align-items: center;
  color: rgba(0, 0, 0, 0.55);
  font-size: 13px;
}

.ls-callout {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 9px;
  background: rgba(0, 0, 0, 0.018);
}

.ls-callout > span,
.ls-callout > div > span {
  display: block;
  margin-top: 3px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.5;
}

.ls-feature-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-height: 64px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 9px;
}

.ls-muted {
  margin-top: 3px;
  color: rgba(0, 0, 0, 0.52);
  font-size: 12px;
  line-height: 1.45;
}

.ls-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.ls-plan-card {
  position: relative;
}

.ls-plan-row {
  display: grid;
  grid-template-columns: minmax(90px, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.ls-plan-row span {
  color: rgba(0, 0, 0, 0.48);
}

.ls-plan-row strong {
  text-align: right;
  overflow-wrap: anywhere;
}

.ls-preflight {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  color: rgba(0, 0, 0, 0.62);
}

.ls-ok {
  color: #389e0d;
}

@media (max-width: 1199px) {
  .ls-plan-card {
    margin-top: 4px;
  }
}

@media (max-width: 767px) {
  .ls-quick-hero {
    flex-direction: column;
  }

  .ls-hero-tags {
    justify-content: flex-start;
  }

  .ls-quick-hero h1 {
    font-size: 26px;
  }
}
</style>
