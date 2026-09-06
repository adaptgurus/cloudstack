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

    <a-alert
      v-if="preflight.message"
      :type="preflight.type"
      show-icon
      :message="preflight.message"
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
            <div class="ls-scope-strip">
              <div>
                <span class="ls-scope-strip__label">Deployment scope</span>
                <strong>{{ deploymentScopeLabel }}</strong>
              </div>
              <a-tag v-if="activeProjectId" color="blue">Project</a-tag>
              <a-tag v-else>Account</a-tag>
            </div>
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
                    :disabled="!kvmSiteReady"
                    placeholder="Select KVM OS Image"
                    @change="onTemplateChange" />
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
                    :disabled="!kvmSiteReady"
                    placeholder="Select Compute Profile" />
                </a-form-item>
              </a-col>
            </a-row>
            <div class="ls-inline-state ls-inline-state--wrap">
              <a-tag color="green">KVM</a-tag>
              <a-tag :color="preflightTagColor(preflight.site)">Site: {{ preflightTagLabel(preflight.site) }}</a-tag>
              <a-tag :color="preflightTagColor(preflight.image)">OS Image: {{ preflightTagLabel(preflight.image) }}</a-tag>
              <span>Other upstream hypervisors are intentionally not exposed by the LayerSentry customer profile.</span>
            </div>
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><database-outlined /> Storage</span>
            </template>

            <a-row :gutter="16">
              <a-col :xs="24" :md="12">
                <a-form-item label="Root Storage Profile override (optional)">
                  <a-select
                    v-model:value="form.rootdiskofferingid"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.storage"
                    :options="rootStorageOptions"
                    :disabled="!kvmSiteReady"
                    placeholder="Use Compute Profile / image default" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Root disk size (GiB, optional)">
                  <a-input-number
                    v-model:value="form.rootdisksize"
                    :min="1"
                    :precision="0"
                    :disabled="!kvmSiteReady"
                    style="width: 100%"
                    placeholder="Use image/profile default" />
                </a-form-item>
              </a-col>
            </a-row>

            <div class="ls-subsection-header">
              <div>
                <strong>Data volumes</strong>
                <div class="ls-muted">Add one or more CloudStack-managed data disks. Device IDs are assigned deterministically.</div>
              </div>
              <a-button
                v-if="storageProfiles.length > 0"
                :disabled="!kvmSiteReady"
                @click="addDataVolume">
                <plus-outlined /> Add data volume
              </a-button>
            </div>

            <div v-if="form.dataVolumes.length === 0" class="ls-empty-row">
              No additional data volumes selected.
            </div>

            <div
              v-for="(volume, index) in form.dataVolumes"
              :key="volume.key"
              class="ls-data-volume">
              <div class="ls-data-volume__header">
                <strong>Data volume {{ index + 1 }}</strong>
                <a-button type="text" danger :aria-label="`Remove data volume ${index + 1}`" @click="removeDataVolume(index)">
                  <delete-outlined />
                </a-button>
              </div>
              <a-row :gutter="12">
                <a-col :xs="24" :md="12">
                  <a-form-item label="Storage Profile">
                    <a-select
                      v-model:value="volume.diskofferingid"
                      show-search
                      option-filter-prop="label"
                      :options="storageOptions"
                      placeholder="Select Storage Profile"
                      @change="onDataVolumeProfileChange(volume)" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomized" :xs="24" :md="12">
                  <a-form-item label="Size (GiB)">
                    <a-input-number v-model:value="volume.size" :min="1" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomizediops" :xs="24" :md="12">
                  <a-form-item label="Minimum IOPS">
                    <a-input-number v-model:value="volume.miniops" :min="0" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
                <a-col v-if="selectedDataOffering(volume)?.iscustomizediops" :xs="24" :md="12">
                  <a-form-item label="Maximum IOPS">
                    <a-input-number v-model:value="volume.maxiops" :min="0" :precision="0" style="width: 100%" />
                  </a-form-item>
                </a-col>
              </a-row>
              <div v-if="selectedDataOffering(volume)" class="ls-volume-facts">
                <span>Device ID {{ index + 1 }}</span>
                <span>{{ selectedDataOffering(volume).storagetype || 'Storage policy managed' }}</span>
                <span v-if="selectedDataOffering(volume).provisioningtype">{{ selectedDataOffering(volume).provisioningtype }} provisioning</span>
              </div>
            </div>

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
                    :disabled="!kvmSiteReady || !canListVpcs"
                    placeholder="Site networks / no VPC"
                    @change="loadNetworks" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="Primary Network Blueprint" name="networkid" :rules="networkRules">
                  <a-select
                    v-model:value="form.networkid"
                    show-search
                    option-filter-prop="label"
                    :loading="loading.networks"
                    :options="networkOptions"
                    :disabled="!kvmSiteReady || selectedZoneNetworkType === 'Basic'"
                    :placeholder="selectedZoneNetworkType === 'Basic' ? 'Managed by the Site' : 'Select primary workload network'"
                    @change="onPrimaryNetworkChange" />
                </a-form-item>
              </a-col>
              <a-col v-if="selectedZoneNetworkType !== 'Basic'" :xs="24" :md="12">
                <a-form-item label="Additional workload networks (optional)">
                  <a-select
                    v-model:value="form.additionalnetworkids"
                    mode="multiple"
                    allow-clear
                    show-search
                    option-filter-prop="label"
                    :loading="loading.networks"
                    :options="additionalNetworkOptions"
                    :disabled="!form.networkid"
                    placeholder="Attach additional networks" />
                </a-form-item>
              </a-col>
              <a-col v-if="canOverrideIp && selectedZoneNetworkType !== 'Basic'" :xs="24" :md="12">
                <a-form-item label="Primary private IP override (optional)">
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
                    <strong>VM HA request</strong>
                    <div class="ls-muted">CloudStack remains authoritative for actual HA eligibility and recovery behavior.</div>
                  </div>
                  <a-tag :color="selectedComputeProfile && selectedComputeProfile.offerha ? 'blue' : 'default'">
                    {{ selectedComputeProfile && selectedComputeProfile.offerha ? 'Requested by Compute Profile' : 'Not requested' }}
                  </a-tag>
                </div>
              </a-col>
              <a-col :xs="24" :md="12">
                <div class="ls-feature-row">
                  <div>
                    <strong>Backup &amp; DR</strong>
                    <div class="ls-muted">Shown only after a real provider, policy and recovery mapping are enabled and certified.</div>
                  </div>
                  <a-tag :color="protectionCapabilityColor">{{ protectionCapabilityLabel }}</a-tag>
                </div>
              </a-col>
            </a-row>
            <a-alert
              type="info"
              show-icon
              message="Quick Provision never marks a VM Protected, HA or DR Ready from UI intent alone. Those states require confirmed backend evidence." />
          </a-card>

          <a-card class="ls-section-card" :bordered="false">
            <template #title>
              <span class="ls-section-title"><check-circle-outlined /> Review, Preflight &amp; Deploy</span>
            </template>

            <a-alert
              v-if="blockingIssues.length"
              type="warning"
              show-icon
              class="ls-review-alert">
              <template #message>Resolve {{ blockingIssues.length }} blocking item{{ blockingIssues.length === 1 ? '' : 's' }} before deployment.</template>
              <template #description>
                <ul class="ls-issue-list">
                  <li v-for="issue in blockingIssues" :key="issue">{{ issue }}</li>
                </ul>
              </template>
            </a-alert>
            <a-alert
              v-else
              type="success"
              show-icon
              class="ls-review-alert"
              message="Core provisioning plan is valid. Run preflight again immediately before deployment." />

            <div class="ls-review-controls">
              <a-checkbox v-model:checked="form.startvm">Start VM after provisioning</a-checkbox>
              <div class="ls-actions">
                <a-button @click="$router.back()">Cancel</a-button>
                <a-button :loading="loading.preflight" :disabled="!form.zoneid" @click="runPreflight">
                  <check-circle-outlined /> Run preflight
                </a-button>
                <a-button type="primary" html-type="submit" :loading="deploying" :disabled="!readyToDeploy">
                  <rocket-outlined /> Provision VM
                </a-button>
              </div>
            </div>
          </a-card>
        </a-form>
      </a-col>

      <a-col :xs="24" :xl="7">
        <a-affix :offset-top="76">
          <a-card class="ls-plan-card" :bordered="false" title="Resolved plan">
            <div class="ls-plan-row"><span>Scope</span><strong>{{ deploymentScopeLabel }}</strong></div>
            <div class="ls-plan-row"><span>Site</span><strong>{{ selectedZone?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Hypervisor</span><strong>KVM</strong></div>
            <div class="ls-plan-row"><span>OS Image</span><strong>{{ selectedTemplate?.displaytext || selectedTemplate?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Compute</span><strong>{{ selectedComputeProfile?.name || 'Not selected' }}</strong></div>
            <div class="ls-plan-row"><span>Root storage</span><strong>{{ selectedRootStorageProfile?.displaytext || selectedRootStorageProfile?.name || 'Default policy' }}</strong></div>
            <div class="ls-plan-row"><span>Root size</span><strong>{{ form.rootdisksize ? `${form.rootdisksize} GiB` : 'Default' }}</strong></div>
            <div class="ls-plan-row"><span>Data volumes</span><strong>{{ form.dataVolumes.length }}</strong></div>
            <div class="ls-plan-row"><span>VPC</span><strong>{{ selectedVpc?.name || 'None' }}</strong></div>
            <div class="ls-plan-row"><span>Primary network</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : (selectedNetwork?.name || 'Not selected') }}</strong></div>
            <div class="ls-plan-row"><span>Additional networks</span><strong>{{ form.additionalnetworkids.length }}</strong></div>
            <div class="ls-plan-row"><span>Private IP</span><strong>{{ form.ipaddress || 'Automatic' }}</strong></div>
            <div class="ls-plan-row"><span>VLAN</span><strong>{{ selectedZoneNetworkType === 'Basic' ? 'Site managed' : resolvedVlan }}</strong></div>
            <a-divider />
            <div class="ls-preflight">
              <check-circle-outlined v-if="readyToDeploy" class="ls-ok" />
              <info-circle-outlined v-else />
              <span>{{ readyToDeploy ? 'KVM and OS Image preflight are current and the provisioning plan has no blocking inputs.' : 'Complete the required inputs and preflight checks.' }}</span>
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
  DeleteOutlined,
  EnvironmentOutlined,
  InfoCircleOutlined,
  PlusOutlined,
  RocketOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons-vue'
import { getAPI, postAPI } from '@/api'
import { checkKvmImage, checkKvmSite } from '@/config/kvmProvisioning'
import { getLayersentryCapabilities, LAYERSENTRY_FEATURES } from '@/config/layersentryCapabilities'
import {
  buildQuickProvisionDeployParams,
  normaliseAdditionalNetworks,
  quickProvisionBlockingIssues
} from './quickProvision'

export default {
  name: 'LayersentryQuickProvision',
  components: {
    ApartmentOutlined,
    CheckCircleOutlined,
    CloudServerOutlined,
    DatabaseOutlined,
    DeleteOutlined,
    EnvironmentOutlined,
    InfoCircleOutlined,
    PlusOutlined,
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
        rootdiskofferingid: undefined,
        rootdisksize: undefined,
        dataVolumes: [],
        vpcid: undefined,
        networkid: undefined,
        additionalnetworkids: [],
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
        networks: false,
        preflight: false
      },
      deploying: false,
      loadError: '',
      nextDataVolumeKey: 0,
      preflight: {
        site: 'idle',
        image: 'idle',
        type: 'info',
        message: ''
      }
    }
  },
  computed: {
    capabilities () {
      return getLayersentryCapabilities(this.$store.getters.apis, this.$config)
    },
    activeProjectId () {
      return this.$store.getters.project?.id || undefined
    },
    deploymentScopeLabel () {
      if (this.activeProjectId) {
        return this.$store.getters.project?.displaytext || this.$store.getters.project?.name || this.activeProjectId
      }
      return this.$store.getters.userInfo?.account || this.$store.getters.userInfo?.accountname || 'Current account'
    },
    canListVpcs () {
      return Boolean(this.$store.getters.apis?.listVPCs)
    },
    canOverrideIp () {
      return ['Admin', 'DomainAdmin'].includes(this.$store.getters.userInfo?.roletype)
    },
    kvmSiteReady () {
      return this.preflight.site === 'ready'
    },
    imageReady () {
      return this.preflight.image === 'ready'
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
    selectedRootStorageProfile () {
      return this.storageProfiles.find(item => item.id === this.form.rootdiskofferingid)
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
    rootStorageOptions () {
      return this.storageProfiles
        .filter(item => !item.iscustomizediops)
        .map(item => ({ label: item.displaytext || item.name, value: item.id }))
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
    additionalNetworkOptions () {
      return this.networkOptions.filter(option => option.value !== this.form.networkid)
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
    blockingIssues () {
      return quickProvisionBlockingIssues({
        form: this.form,
        networkType: this.selectedZoneNetworkType,
        storageProfiles: this.storageProfiles,
        kvmSiteReady: this.kvmSiteReady,
        imageReady: this.imageReady
      })
    },
    readyToDeploy () {
      return this.blockingIssues.length === 0 && !this.loading.preflight
    },
    networkDescriptionColumns () {
      return window.innerWidth < 900 ? 1 : 2
    },
    protectionCapabilityLabel () {
      const backup = this.capabilities[LAYERSENTRY_FEATURES.BACKUP]
      const dr = this.capabilities[LAYERSENTRY_FEATURES.DR]
      if (backup?.visible || dr?.visible) return 'Available by policy'
      if (backup?.enabled || dr?.enabled) return 'Prerequisites not ready'
      return 'Not enabled'
    },
    protectionCapabilityColor () {
      const backup = this.capabilities[LAYERSENTRY_FEATURES.BACKUP]
      const dr = this.capabilities[LAYERSENTRY_FEATURES.DR]
      if (backup?.visible || dr?.visible) return 'blue'
      if (backup?.enabled || dr?.enabled) return 'orange'
      return 'default'
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
    errorMessage (error, fallback) {
      const key = error?.message
      if (key && key.startsWith('message.')) return this.$t(key)
      return fallback
    },
    preflightTagColor (state) {
      if (state === 'ready') return 'green'
      if (state === 'checking') return 'blue'
      if (state === 'error') return 'red'
      return 'default'
    },
    preflightTagLabel (state) {
      if (state === 'ready') return 'Verified'
      if (state === 'checking') return 'Checking'
      if (state === 'error') return 'Blocked'
      return 'Not checked'
    },
    async loadZones () {
      this.loading.zones = true
      this.loadError = ''
      try {
        const response = await getAPI('listZones', { showicon: true })
        this.zones = this.responseItems(response, 'listzonesresponse', 'zone')
        if (this.zones.length === 1) {
          this.form.zoneid = this.zones[0].id
          await this.onZoneChange()
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
      this.form.rootdiskofferingid = undefined
      this.form.rootdisksize = undefined
      this.form.dataVolumes = []
      this.form.vpcid = undefined
      this.form.networkid = undefined
      this.form.additionalnetworkids = []
      this.form.ipaddress = ''
      this.templates = []
      this.computeProfiles = []
      this.storageProfiles = []
      this.vpcs = []
      this.networks = []
      this.preflight.image = 'idle'
      this.preflight.message = ''
    },
    async validateSiteKvm () {
      if (!this.form.zoneid) {
        this.preflight.site = 'idle'
        return false
      }
      const zoneId = this.form.zoneid
      this.preflight.site = 'checking'
      try {
        await checkKvmSite(getAPI, zoneId)
        if (zoneId !== this.form.zoneid) return false
        this.preflight.site = 'ready'
        return true
      } catch (error) {
        if (zoneId !== this.form.zoneid) return false
        this.preflight.site = 'error'
        this.loadError = this.errorMessage(error, 'KVM availability could not be verified for this Site.')
        return false
      }
    },
    async onZoneChange () {
      this.resetZoneDependencies()
      this.loadError = ''
      if (!this.form.zoneid) {
        this.preflight.site = 'idle'
        return
      }
      const siteReady = await this.validateSiteKvm()
      if (!siteReady) return
      const zoneId = this.form.zoneid
      await Promise.all([
        this.loadTemplates(),
        this.loadComputeProfiles(),
        this.loadStorageProfiles(),
        this.loadVpcs()
      ])
      if (zoneId !== this.form.zoneid) return
      await this.loadNetworks()
      if (this.form.templateid) await this.validateSelectedImage()
    },
    async loadTemplates () {
      this.loading.templates = true
      try {
        const response = await getAPI('listTemplates', {
          templatefilter: 'executable',
          zoneid: this.form.zoneid,
          hypervisor: 'KVM',
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
      this.form.additionalnetworkids = []
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
    onPrimaryNetworkChange () {
      this.form.additionalnetworkids = normaliseAdditionalNetworks(this.form.networkid, this.form.additionalnetworkids)
      this.form.ipaddress = ''
    },
    async onTemplateChange () {
      this.preflight.image = 'idle'
      this.preflight.message = ''
      await this.validateSelectedImage()
    },
    async validateSelectedImage () {
      if (!this.form.zoneid || !this.form.templateid) {
        this.preflight.image = 'idle'
        return false
      }
      const zoneId = this.form.zoneid
      const templateId = this.form.templateid
      this.preflight.image = 'checking'
      try {
        const scope = this.activeProjectId ? { projectid: this.activeProjectId } : {}
        await checkKvmImage(getAPI, zoneId, 'templateid', templateId, scope)
        if (zoneId !== this.form.zoneid || templateId !== this.form.templateid) return false
        this.preflight.image = 'ready'
        return true
      } catch (error) {
        if (zoneId !== this.form.zoneid || templateId !== this.form.templateid) return false
        this.preflight.image = 'error'
        this.preflight.type = 'error'
        this.preflight.message = this.errorMessage(error, 'The selected OS Image failed the KVM preflight.')
        return false
      }
    },
    addDataVolume () {
      this.nextDataVolumeKey += 1
      this.form.dataVolumes.push({
        key: this.nextDataVolumeKey,
        diskofferingid: undefined,
        size: undefined,
        miniops: undefined,
        maxiops: undefined
      })
    },
    removeDataVolume (index) {
      this.form.dataVolumes.splice(index, 1)
    },
    selectedDataOffering (volume) {
      return this.storageProfiles.find(item => item.id === volume?.diskofferingid)
    },
    onDataVolumeProfileChange (volume) {
      const offering = this.selectedDataOffering(volume)
      if (!offering?.iscustomized) volume.size = undefined
      if (!offering?.iscustomizediops) {
        volume.miniops = undefined
        volume.maxiops = undefined
      }
    },
    buildDeployParams () {
      return buildQuickProvisionDeployParams({
        form: this.form,
        networkType: this.selectedZoneNetworkType,
        storageProfiles: this.storageProfiles,
        projectId: this.activeProjectId
      })
    },
    async runPreflight () {
      if (this.loading.preflight) return false
      this.loading.preflight = true
      this.preflight.message = ''
      this.preflight.type = 'info'
      try {
        const siteReady = await this.validateSiteKvm()
        if (siteReady) await this.validateSelectedImage()
        const issues = this.blockingIssues
        if (issues.length > 0) {
          this.preflight.type = 'warning'
          this.preflight.message = `Preflight is blocked by ${issues.length} unresolved item${issues.length === 1 ? '' : 's'}.`
          return false
        }
        this.preflight.type = 'success'
        this.preflight.message = 'Preflight passed for the current Site, KVM OS Image and provisioning inputs.'
        return true
      } finally {
        this.loading.preflight = false
      }
    },
    async deploy () {
      if (this.deploying) return
      const passed = await this.runPreflight()
      if (!passed) return
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

.ls-inline-state--wrap {
  flex-wrap: wrap;
}

.ls-scope-strip,
.ls-subsection-header,
.ls-data-volume__header,
.ls-review-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ls-scope-strip {
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #eaecf0;
  border-radius: 8px;
}

.ls-scope-strip__label {
  display: block;
  margin-bottom: 2px;
  color: #667085;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ls-subsection-header {
  margin: 8px 0 12px;
}

.ls-empty-row {
  margin-bottom: 14px;
  padding: 16px;
  color: #667085;
  background: #f9fafb;
  border: 1px dashed #d0d5dd;
  border-radius: 9px;
  text-align: center;
}

.ls-data-volume {
  margin-bottom: 12px;
  padding: 12px 14px 4px;
  border: 1px solid #e4e7ec;
  border-radius: 9px;
  background: #fff;
}

.ls-data-volume__header {
  margin-bottom: 2px;
}

.ls-volume-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin: -2px 0 10px;
  color: #667085;
  font-size: 12px;
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
  min-height: 76px;
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

.ls-review-alert {
  margin-bottom: 14px;
}

.ls-issue-list {
  margin: 8px 0 0 18px;
  padding: 0;
}

.ls-review-controls {
  align-items: flex-end;
  flex-wrap: wrap;
}

.ls-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
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
  .ls-quick-hero,
  .ls-review-controls,
  .ls-subsection-header {
    flex-direction: column;
    align-items: stretch;
  }

  .ls-hero-tags {
    justify-content: flex-start;
  }

  .ls-quick-hero h1 {
    font-size: 26px;
  }

  .ls-actions {
    justify-content: stretch;
  }

  .ls-actions .ant-btn {
    flex: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto !important;
  }
}
</style>
