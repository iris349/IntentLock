import { useState } from 'react'

type Role = 'user' | 'admin'
type ExportField = 'name' | 'email' | 'phone' | 'department'

type User = {
  id: number
  username: string
  role: Role
}

type Employee = {
  id: number
  name: string
  email: string
  phone: string
  department: string
  role: Role
}

type AuditLog = {
  id: number
  actor_user_id: number
  action: string
  target_id: number | null
  details: Record<string, unknown>
  created_at: string
}

type RoleChange = {
  employee: Employee
  newRole: Role
}

type ExportSelection = {
  employeeIds: number[]
  fields: ExportField[]
}

const FIELD_OPTIONS: { value: ExportField; label: string }[] = [
  { value: 'name', label: '이름' },
  { value: 'email', label: '이메일' },
  { value: 'phone', label: '전화번호' },
  { value: 'department', label: '부서' },
]

function roleLabel(role: Role) {
  return role === 'admin' ? '관리자' : '일반 사용자'
}

async function ensureSuccess(response: Response) {
  if (response.ok) return

  let message = `요청 실패 (${response.status})`

  try {
    const data = await response.json()

    if (typeof data.detail === 'string') {
      message = data.detail
    } else if (data.detail) {
      message = JSON.stringify(data.detail)
    }
  } catch {
    // JSON이 아닌 오류 응답은 기본 메시지 사용
  }

  throw new Error(message)
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '요청에 실패했습니다.'
}

function App() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // 실습에서는 토큰을 메모리에 보관
  const [token, setToken] = useState('')
  const [user, setUser] = useState<User | null>(null)

  const [employees, setEmployees] = useState<Employee[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])

  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [selectedFields, setSelectedFields] = useState<ExportField[]>([
    'name',
    'email',
  ])

  const [pendingRole, setPendingRole] = useState<RoleChange | null>(null)
  const [pendingExport, setPendingExport] =
    useState<ExportSelection | null>(null)

  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function authorizedFetch(
    path: string,
    accessToken: string,
    options: RequestInit = {},
  ) {
    const headers = new Headers(options.headers)
    headers.set('Authorization', `Bearer ${accessToken}`)

    const response = await fetch(`/api${path}`, {
      ...options,
      headers,
    })

    await ensureSuccess(response)
    return response
  }

  async function loadAdminData(accessToken: string) {
    const [employeeResponse, logResponse] = await Promise.all([
      authorizedFetch('/employees', accessToken),
      authorizedFetch('/audit-logs', accessToken),
    ])

    const employeeData: Employee[] = await employeeResponse.json()
    const logData: AuditLog[] = await logResponse.json()

    setEmployees(employeeData)
    setLogs(logData)
  }

  async function login() {
    setBusy(true)
    setMessage('')

    try {
      const form = new URLSearchParams({
        username,
        password,
      })

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: form,
      })

      await ensureSuccess(response)

      const data: { access_token: string } = await response.json()

      const meResponse = await authorizedFetch(
        '/auth/me',
        data.access_token,
      )

      const currentUser: User = await meResponse.json()

      if (currentUser.role === 'admin') {
        await loadAdminData(data.access_token)
      }

      setToken(data.access_token)
      setUser(currentUser)
      setPassword('')
      setMessage('로그인했습니다.')
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  function logout() {
    setToken('')
    setUser(null)
    setEmployees([])
    setLogs([])
    setSelectedIds([])
    setPendingRole(null)
    setPendingExport(null)
    setPassword('')
    setMessage('로그아웃했습니다.')
  }

  function toggleEmployee(id: number) {
    setSelectedIds((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : [...previous, id],
    )
  }

  function toggleField(field: ExportField) {
    setSelectedFields((previous) =>
      previous.includes(field)
        ? previous.filter((value) => value !== field)
        : [...previous, field],
    )
  }

  async function executeRoleChange() {
    if (!pendingRole) return

    const selection = pendingRole
    setBusy(true)
    setMessage('')

    try {
      const response = await authorizedFetch(
        `/employees/${selection.employee.id}/role`,
        token,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: selection.newRole }),
        },
      )

      const updated: Employee = await response.json()

      setEmployees((previous) =>
        previous.map((employee) =>
          employee.id === updated.id ? updated : employee,
        ),
      )

      setPendingRole(null)
      setMessage(`${updated.name}의 권한을 변경했습니다.`)

      try {
        await loadAdminData(token)
      } catch {
        setMessage('권한 변경은 성공했지만 목록·기록 새로고침에 실패했습니다.')
      }
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  function prepareExport() {
    if (selectedIds.length === 0 || selectedFields.length === 0) {
      setMessage('직원과 내보낼 항목을 각각 하나 이상 선택하세요.')
      return
    }

    setMessage('')
    setPendingExport({
      employeeIds: [...selectedIds],
      fields: [...selectedFields],
    })
  }

  async function executeExport() {
    if (!pendingExport) return

    const selection = pendingExport
    setBusy(true)
    setMessage('')

    try {
      const response = await authorizedFetch('/exports', token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_ids: selection.employeeIds,
          fields: selection.fields,
        }),
      })

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = url
      link.download = 'employees.csv'
      document.body.appendChild(link)
      link.click()
      link.remove()

      window.setTimeout(() => URL.revokeObjectURL(url), 1000)

      setPendingExport(null)
      setMessage('CSV 다운로드를 요청했습니다.')

      try {
        await loadAdminData(token)
      } catch {
        setMessage('CSV 생성은 성공했지만 목록·기록 새로고침에 실패했습니다.')
      }
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function refreshData() {
    setBusy(true)

    try {
      await loadAdminData(token)
      setMessage('목록과 기록을 새로고침했습니다.')
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <h1>IntentLock 실습 서비스</h1>
      <p>직원 권한 변경 · 개인정보 내보내기</p>

      <p role="status">{message}</p>

      {!user ? (
        <section>
          <h2>로그인</h2>

          <form
            onSubmit={(event) => {
              event.preventDefault()
              void login()
            }}
          >
            <label>
              아이디
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
                disabled={busy}
              />
            </label>

            <label>
              비밀번호
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={busy}
              />
            </label>

            <button type="submit" disabled={busy}>
              {busy ? '로그인 중...' : '로그인'}
            </button>
          </form>
        </section>
      ) : (
        <>
          <section className="toolbar">
            <span>
              {user.username} · {roleLabel(user.role)}
            </span>
            <button onClick={logout} disabled={busy}>
              로그아웃
            </button>
          </section>

          {user.role !== 'admin' ? (
            <p>직원 관리와 개인정보 내보내기는 관리자만 사용할 수 있습니다.</p>
          ) : (
            <>
              <section>
                <h2>직원 목록 · 권한 변경</h2>

                <button onClick={refreshData} disabled={busy}>
                  목록·기록 새로고침
                </button>

                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>내보내기 선택</th>
                        <th>이름</th>
                        <th>이메일</th>
                        <th>부서</th>
                        <th>현재 권한</th>
                        <th>권한 변경</th>
                      </tr>
                    </thead>

                    <tbody>
                      {employees.map((employee) => (
                        <tr key={employee.id}>
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`${employee.name} 내보내기 선택`}
                              checked={selectedIds.includes(employee.id)}
                              onChange={() => toggleEmployee(employee.id)}
                              disabled={busy}
                            />
                          </td>
                          <td>{employee.name}</td>
                          <td>{employee.email}</td>
                          <td>{employee.department}</td>
                          <td>{roleLabel(employee.role)}</td>
                          <td>
                            <button
                              disabled={
                                busy ||
                                pendingRole !== null ||
                                pendingExport !== null
                              }
                              onClick={() => {
                                setMessage('')
                                setPendingRole({
                                  employee: { ...employee },
                                  newRole:
                                    employee.role === 'user' ? 'admin' : 'user',
                                })
                              }}
                            >
                              {employee.role === 'user'
                                ? '관리자로 변경'
                                : '일반 사용자로 변경'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section>
                <h2>개인정보 내보내기</h2>
                <p>선택한 직원: {selectedIds.length}명</p>

                <div className="field-options">
                  {FIELD_OPTIONS.map((field) => (
                    <label key={field.value}>
                      <input
                        type="checkbox"
                        checked={selectedFields.includes(field.value)}
                        onChange={() => toggleField(field.value)}
                        disabled={busy}
                      />
                      {field.label}
                    </label>
                  ))}
                </div>

                <button
                  onClick={prepareExport}
                  disabled={
                    busy ||
                    pendingRole !== null ||
                    pendingExport !== null
                  }
                >
                  내보내기 내용 확인
                </button>
              </section>

              <section>
                <h2>실행 기록</h2>

                {logs.length === 0 ? (
                  <p>실행 기록이 없습니다.</p>
                ) : (
                  <ul>
                    {logs.map((log) => (
                      <li key={log.id}>
                        <strong>
                          {log.action === 'employee_role_change'
                            ? '권한 변경'
                            : log.action === 'employee_export'
                              ? '개인정보 내보내기'
                              : log.action}
                        </strong>
                        {' · '}
                        {new Date(log.created_at).toLocaleString('ko-KR')}
                        {' · 실행 계정 번호: '}
                        {log.actor_user_id}
                        {log.target_id !== null &&
                          ` · 대상 직원 번호: ${log.target_id}`}
                        <pre>{JSON.stringify(log.details, null, 2)}</pre>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {pendingRole && (
                <div className="modal-backdrop">
                  <section
                    className="modal"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="role-confirm-title"
                  >
                    <h2 id="role-confirm-title">권한 변경 확인</h2>
                    <p>
                      대상: {pendingRole.employee.name}
                      {' '}({pendingRole.employee.email})
                    </p>
                    <p>
                      기존 권한: {roleLabel(pendingRole.employee.role)}
                    </p>
                    <p>변경할 권한: {roleLabel(pendingRole.newRole)}</p>

                    <div className="toolbar">
                      <button
                        onClick={executeRoleChange}
                        disabled={busy}
                      >
                        {busy ? '처리 중...' : '확인 후 권한 변경'}
                      </button>
                      <button
                        onClick={() => setPendingRole(null)}
                        disabled={busy}
                      >
                        취소
                      </button>
                    </div>

                    <p role="status">{message}</p>
                  </section>
                </div>
              )}

              {pendingExport && (
                <div className="modal-backdrop">
                  <section
                    className="modal"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="export-confirm-title"
                  >
                    <h2 id="export-confirm-title">개인정보 내보내기 확인</h2>
                    <p>대상 인원: {pendingExport.employeeIds.length}명</p>

                    <p>대상 직원:</p>
        
                  

                    <ul>
                      {pendingExport.employeeIds.map((id) => {
                        const employee = employees.find(
                          (item) => item.id === id,
                        )

                        return (
                          <li key={id}>
                            {employee?.name ?? `직원 ${id}`}
                            {employee && ` (${employee.email})`}
                          </li>
                        )
                      })}
                    </ul>

                    <p>
                      내보낼 항목:{' '}
                      {pendingExport.fields
                        .map(
                          (field) =>
                            FIELD_OPTIONS.find(
                              (option) => option.value === field,
                            )?.label,
                        )
                        .join(', ')}
                    </p>

                    <div className="toolbar">
                      <button onClick={executeExport} disabled={busy}>
                        {busy ? '처리 중...' : '확인 후 CSV 다운로드'}
                      </button>
                      <button
                        onClick={() => setPendingExport(null)}
                        disabled={busy}
                      >
                        취소
                      </button>
                    </div>

                    <p role="status">{message}</p>
                  </section>
                </div>
              )}
            </>
          )}
        </>
      )}
    </main>
  )
}

export default App