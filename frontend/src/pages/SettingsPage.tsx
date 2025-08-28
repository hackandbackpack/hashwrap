import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, Webhook, Shield, Plus } from 'lucide-react'

import { usersApi, webhooksApi } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDate } from '@/lib/utils'

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'webhooks' | 'profiles'>('users')

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.getUsers,
  })

  const { data: webhooks, isLoading: webhooksLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn: webhooksApi.getWebhooks,
  })

  const tabs = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'webhooks', label: 'Webhooks', icon: Webhook },
    { id: 'profiles', label: 'Profiles', icon: Shield },
  ] as const

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage users, webhooks, and system configuration
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-border">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'users' && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>User Management</CardTitle>
                  <CardDescription>
                    Manage user accounts and permissions
                  </CardDescription>
                </div>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Add User
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {usersLoading ? (
                <LoadingSpinner />
              ) : users && users.length > 0 ? (
                <div className="space-y-4">
                  {users.map((user) => (
                    <div
                      key={user.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div>
                        <h3 className="font-medium">{user.email}</h3>
                        <div className="flex items-center space-x-2 mt-1">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${
                            user.role === 'admin' ? 'bg-destructive/10 text-destructive' :
                            user.role === 'operator' ? 'bg-warning/10 text-warning' :
                            'bg-muted text-muted-foreground'
                          }`}>
                            {user.role.toUpperCase()}
                          </span>
                          <span className={`px-2 py-1 text-xs font-medium rounded ${
                            user.is_active ? 'bg-success/10 text-success' : 'bg-muted text-muted-foreground'
                          }`}>
                            {user.is_active ? 'ACTIVE' : 'INACTIVE'}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          Last login: {user.last_login ? formatDate(user.last_login) : 'Never'}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button variant="outline" size="sm">
                          Edit
                        </Button>
                        <Button variant="destructive" size="sm">
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">
                  No users found
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {activeTab === 'webhooks' && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Webhook Configuration</CardTitle>
                  <CardDescription>
                    Configure webhooks for job notifications and events
                  </CardDescription>
                </div>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Webhook
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {webhooksLoading ? (
                <LoadingSpinner />
              ) : webhooks && webhooks.length > 0 ? (
                <div className="space-y-4">
                  {webhooks.map((webhook) => (
                    <div
                      key={webhook.id}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div>
                        <h3 className="font-medium">{webhook.name}</h3>
                        <p className="text-sm text-muted-foreground">{webhook.url}</p>
                        <div className="flex items-center space-x-2 mt-1">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${
                            webhook.is_active ? 'bg-success/10 text-success' : 'bg-muted text-muted-foreground'
                          }`}>
                            {webhook.is_active ? 'ACTIVE' : 'INACTIVE'}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {webhook.events.length} event{webhook.events.length !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button variant="outline" size="sm">
                          Test
                        </Button>
                        <Button variant="outline" size="sm">
                          Edit
                        </Button>
                        <Button variant="destructive" size="sm">
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">
                  No webhooks configured
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {activeTab === 'profiles' && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Attack Profiles</CardTitle>
                  <CardDescription>
                    Manage attack profiles for different cracking scenarios
                  </CardDescription>
                </div>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Profile
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-center text-muted-foreground py-8">
                Profile management coming soon
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}