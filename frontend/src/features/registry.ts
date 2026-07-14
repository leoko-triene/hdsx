import type {Component} from 'vue'
import type {RouteRecordRaw} from 'vue-router'

export interface NavItem {
  to: string
  label: string
  roles: string[]
}

export interface DashboardCard {
  title: string
  text: string
  to: string
  roles: string[]
  icon?: string
}

export interface FeatureModule {
  name: string
  route?: RouteRecordRaw
  navItem?: NavItem
  dashboardCard?: DashboardCard
  actions?: Record<string, Component>
}

const registeredFeatures: FeatureModule[] = []

export function registerFeature(feature: FeatureModule) {
  if (registeredFeatures.some(f => f.name === feature.name)) {
    console.warn(`Feature "${feature.name}" has already been registered.`)
    return
  }
  registeredFeatures.push(feature)
}

export function getRegisteredFeatures(): readonly FeatureModule[] {
  return registeredFeatures
}

export function getFeatureRoutes(): RouteRecordRaw[] {
  return registeredFeatures.map(f => f.route).filter(Boolean) as RouteRecordRaw[]
}

export function getFeatureNavItems(): NavItem[] {
  return registeredFeatures.map(f => f.navItem).filter(Boolean) as NavItem[]
}

export function getFeatureDashboardCards(): DashboardCard[] {
  return registeredFeatures.map(f => f.dashboardCard).filter(Boolean) as DashboardCard[]
}

export function getFeatureActions(slot: string): Component[] {
  return registeredFeatures
    .map(f => f.actions?.[slot])
    .filter(Boolean) as Component[]
}
