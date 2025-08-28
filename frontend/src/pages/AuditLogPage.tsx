import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Search, Filter, Download } from 'lucide-react'

import { auditApi } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDate } from '@/lib/utils'

export const AuditLogPage: React.FC = () => {
  const [filters, setFilters] = useState({
    action: '',
    resource_type: '',
    start_date: '',
    end_date: '',
  })

  const { data: auditLogs, isLoading } = useQuery({
    queryKey: ['audit', 'logs', filters],
    queryFn: () => auditApi.getAuditLogs({
      action: filters.action || undefined,
      resource_type: filters.resource_type || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
      page: 1,
      size: 50,
    }),
  })

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setFilters({
      action: '',
      resource_type: '',
      start_date: '',
      end_date: '',
    })
  }

  const getActionColor = (action: string) => {
    const colors: Record<string, string> = {
      create: 'bg-success/10 text-success',
      update: 'bg-info/10 text-info',
      delete: 'bg-destructive/10 text-destructive',
      login: 'bg-primary/10 text-primary',
      logout: 'bg-muted text-muted-foreground',
    }
    return colors[action.toLowerCase()] || 'bg-muted text-muted-foreground'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Audit Log</h1>
          <p className="text-muted-foreground">
            View system activity and user actions for compliance
          </p>
        </div>
        
        <Button variant="outline">
          <Download className="w-4 h-4 mr-2" />
          Export
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filters</CardTitle>
          <CardDescription>
            Filter audit logs by action, resource, or date range
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <Label htmlFor="action">Action</Label>
              <select
                id="action"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={filters.action}
                onChange={(e) => handleFilterChange('action', e.target.value)}
              >
                <option value="">All Actions</option>
                <option value="create">Create</option>
                <option value="update">Update</option>
                <option value="delete">Delete</option>
                <option value="login">Login</option>
                <option value="logout">Logout</option>
              </select>
            </div>

            <div>
              <Label htmlFor="resource">Resource Type</Label>
              <select
                id="resource"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={filters.resource_type}
                onChange={(e) => handleFilterChange('resource_type', e.target.value)}
              >
                <option value="">All Resources</option>
                <option value="user">User</option>
                <option value="project">Project</option>
                <option value="job">Job</option>
                <option value="upload">Upload</option>
                <option value="webhook">Webhook</option>
              </select>
            </div>

            <div>
              <Label htmlFor="start-date">Start Date</Label>
              <Input
                id="start-date"
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="end-date">End Date</Label>
              <Input
                id="end-date"
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
              />
            </div>

            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={clearFilters}
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit Logs */}
      <Card>
        <CardHeader>
          <CardTitle>
            Activity Log
            {auditLogs && (
              <span className="text-base font-normal text-muted-foreground ml-2">
                ({auditLogs.total.toLocaleString()} total)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <LoadingSpinner />
            </div>
          ) : auditLogs && auditLogs.items.length > 0 ? (
            <div className="space-y-3">
              {auditLogs.items.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start justify-between p-4 border rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${getActionColor(log.action)}`}>
                        {log.action.toUpperCase()}
                      </span>
                      <span className="px-2 py-1 text-xs font-medium bg-muted text-muted-foreground rounded">
                        {log.resource_type.toUpperCase()}
                      </span>
                    </div>
                    
                    <p className="text-sm font-medium mb-1">
                      {log.action} {log.resource_type}
                      {log.resource_id && ` (ID: ${log.resource_id.slice(0, 8)}...)`}
                    </p>
                    
                    <div className="text-xs text-muted-foreground space-y-1">
                      <p>User ID: {log.user_id.slice(0, 8)}...</p>
                      <p>IP: {log.ip_address}</p>
                      <p>Time: {formatDate(log.created_at)}</p>
                    </div>

                    {(log.old_values || log.new_values) && (
                      <details className="mt-2">
                        <summary className="text-xs cursor-pointer text-primary">
                          View Changes
                        </summary>
                        <div className="mt-2 p-2 bg-muted rounded text-xs">
                          {log.old_values && (
                            <div className="mb-2">
                              <p className="font-medium">Old Values:</p>
                              <pre className="text-xs overflow-x-auto">
                                {JSON.stringify(log.old_values, null, 2)}
                              </pre>
                            </div>
                          )}
                          {log.new_values && (
                            <div>
                              <p className="font-medium">New Values:</p>
                              <pre className="text-xs overflow-x-auto">
                                {JSON.stringify(log.new_values, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              ))}

              {/* Pagination */}
              {auditLogs.total > auditLogs.items.length && (
                <div className="text-center py-4">
                  <p className="text-sm text-muted-foreground mb-2">
                    Showing {auditLogs.items.length} of {auditLogs.total.toLocaleString()} entries
                  </p>
                  <Button variant="outline">
                    Load More
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No audit entries</h3>
              <p className="text-muted-foreground">
                {Object.values(filters).some(f => f) 
                  ? 'No entries match your current filters'
                  : 'No audit entries have been recorded yet'
                }
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}