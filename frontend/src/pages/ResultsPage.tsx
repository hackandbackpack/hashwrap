import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Download, Eye, EyeOff, Copy } from 'lucide-react'

import { resultsApi } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDate, copyToClipboard, truncateHash } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

export const ResultsPage: React.FC = () => {
  const { hasRole } = useAuth()
  const [searchQuery, setSearchQuery] = useState('')
  const [hashType, setHashType] = useState('')
  const [revealedPasswords, setRevealedPasswords] = useState<Set<string>>(new Set())

  const { data: results, isLoading } = useQuery({
    queryKey: ['results', 'search', searchQuery, hashType],
    queryFn: () => resultsApi.searchResults({
      query: searchQuery || undefined,
      hash_type: hashType || undefined,
      page: 1,
      size: 50,
    }),
  })

  const handleRevealPassword = async (resultId: string) => {
    try {
      const password = await resultsApi.revealPassword(resultId)
      setRevealedPasswords(prev => new Set(prev).add(resultId))
    } catch (error) {
      console.error('Failed to reveal password:', error)
    }
  }

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const blob = await resultsApi.exportResults({
        format,
        hash_type: hashType || undefined,
      })
      
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `hashwrap-results-${Date.now()}.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Results</h1>
          <p className="text-muted-foreground">
            Search and export your cracked hash results
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={() => handleExport('csv')}
          >
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => handleExport('json')}
          >
            <Download className="w-4 h-4 mr-2" />
            Export JSON
          </Button>
        </div>
      </div>

      {/* Search Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Search Filters</CardTitle>
          <CardDescription>
            Filter results by hash, password, or hash type
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="search">Search Query</Label>
              <div className="relative">
                <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search hashes or passwords..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            
            <div>
              <Label htmlFor="hash-type">Hash Type</Label>
              <select
                id="hash-type"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={hashType}
                onChange={(e) => setHashType(e.target.value)}
              >
                <option value="">All Types</option>
                <option value="MD5">MD5</option>
                <option value="SHA1">SHA1</option>
                <option value="SHA256">SHA256</option>
                <option value="NTLM">NTLM</option>
                <option value="bcrypt">bcrypt</option>
              </select>
            </div>

            <div className="flex items-end">
              <Button
                onClick={() => {
                  setSearchQuery('')
                  setHashType('')
                }}
                variant="outline"
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader>
          <CardTitle>
            Cracked Hashes
            {results && (
              <span className="text-base font-normal text-muted-foreground ml-2">
                ({results.total.toLocaleString()} total)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <LoadingSpinner />
            </div>
          ) : results && results.items.length > 0 ? (
            <div className="space-y-4">
              {results.items.map((result) => (
                <div
                  key={result.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-2">
                      <span className="px-2 py-1 text-xs font-medium bg-primary/10 text-primary rounded">
                        {result.hash_type}
                      </span>
                      <span className="px-2 py-1 text-xs font-medium bg-muted text-muted-foreground rounded">
                        {result.crack_method}
                      </span>
                    </div>
                    
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <Label className="text-xs text-muted-foreground w-12 shrink-0">Hash:</Label>
                        <code className="text-sm font-mono break-all">
                          {truncateHash(result.hash_value, 32)}
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(result.hash_value)}
                        >
                          <Copy className="w-3 h-3" />
                        </Button>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <Label className="text-xs text-muted-foreground w-12 shrink-0">Plain:</Label>
                        {revealedPasswords.has(result.id) ? (
                          <div className="flex items-center space-x-2">
                            <code className="text-sm font-mono">{result.plaintext}</code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(result.plaintext)}
                            >
                              <Copy className="w-3 h-3" />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2">
                            <span className="text-sm text-muted-foreground">••••••••</span>
                            {hasRole(['admin', 'operator']) && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRevealPassword(result.id)}
                              >
                                <Eye className="w-3 h-3" />
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <p className="text-xs text-muted-foreground mt-2">
                      Cracked {formatDate(result.crack_time)}
                    </p>
                  </div>
                </div>
              ))}
              
              {/* Pagination would go here */}
              {results.total > results.items.length && (
                <div className="text-center py-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {results.items.length} of {results.total.toLocaleString()} results
                  </p>
                  <Button variant="outline" className="mt-2">
                    Load More
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Search className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No results found</h3>
              <p className="text-muted-foreground">
                {searchQuery || hashType
                  ? 'Try adjusting your search filters'
                  : 'No hashes have been cracked yet. Run some jobs to see results here.'
                }
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}