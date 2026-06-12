import { createContext, useContext, useEffect, useState } from 'react'
import client from '../api/client'
import { connectEcho, disconnectEcho } from '../echo'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    client
      .get('auth/me')
      .then((res) => {
        setUser(res.data)
        connectEcho(token)
      })
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (email, password) => {
    const res = await client.post('auth/login', { email, password })
    localStorage.setItem('token', res.data.access_token)
    setUser(res.data.user)
    connectEcho(res.data.access_token)
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }

  const logout = async () => {
    try {
      await client.post('auth/logout')
    } catch {
      // token may already be invalid; clear local state regardless
    }
    localStorage.removeItem('token')
    disconnectEcho()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
