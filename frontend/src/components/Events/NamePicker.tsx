import { useQuery } from "@tanstack/react-query"
import { useEffect, useId, useState } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export type NameMatch = {
  id: string
  name: string
  hint?: string
}

type NamePickerProps = {
  label: string
  placeholder: string
  queryKey: string
  search: (query: string) => Promise<NameMatch[]>
  id: string
  selectedName: string
  onPick: (id: string, name: string) => void
  error?: string
}

function optionName(match: NameMatch) {
  return match.hint ? `${match.name} ${match.hint}` : match.name
}

const NamePicker = ({
  label,
  placeholder,
  queryKey,
  search,
  id,
  selectedName,
  onPick,
  error,
}: NamePickerProps) => {
  const inputId = useId()
  const listId = useId()
  const [text, setText] = useState(selectedName)
  const [debounced, setDebounced] = useState(selectedName)
  const [open, setOpen] = useState(false)
  const query = debounced.trim()

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(text), 250)
    return () => clearTimeout(handle)
  }, [text])

  const { data, isFetching } = useQuery({
    queryKey: [queryKey, query],
    queryFn: () => search(query),
    enabled: open && query.length > 0,
  })

  return (
    <div className="grid gap-2">
      <Label htmlFor={inputId}>
        {label} <span className="text-destructive">*</span>
      </Label>
      <Input
        id={inputId}
        placeholder={placeholder}
        type="text"
        value={text}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={error ? true : undefined}
        onChange={(event) => {
          setText(event.target.value)
          setOpen(true)
          if (id) {
            onPick("", "")
          }
        }}
      />
      {open && query.length > 0 && (
        <div id={listId} role="listbox" className="rounded-md border">
          {isFetching && (
            <p className="text-muted-foreground px-3 py-2 text-sm">
              Searching…
            </p>
          )}
          {!isFetching && data?.length === 0 && (
            <p className="text-muted-foreground px-3 py-2 text-sm">
              No matches
            </p>
          )}
          {data?.map((match) => (
            <button
              key={match.id}
              type="button"
              role="option"
              className="hover:bg-accent block w-full px-3 py-2 text-left text-sm"
              onClick={() => {
                setText(match.name)
                setOpen(false)
                onPick(match.id, match.name)
              }}
            >
              {optionName(match)}
            </button>
          ))}
        </div>
      )}
      {error && <p className="text-destructive text-sm">{error}</p>}
    </div>
  )
}

export default NamePicker
