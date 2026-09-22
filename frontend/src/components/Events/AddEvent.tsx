import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type EventCreate, EventsService } from "@/client"
import NamePicker from "@/components/Events/NamePicker"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  name: z.string().min(1, { message: "Name is required" }),
  description: z.string().optional(),
  venue_id: z.string().min(1, { message: "Choose a venue" }),
  performer_id: z.string().min(1, { message: "Choose a performer" }),
  time: z.string().min(1, { message: "Time is required" }),
  price: z
    .string()
    .min(1, { message: "Price is required" })
    .refine((value) => Number(value) >= 0, {
      message: "Price must be 0 or more",
    }),
})

type FormData = z.infer<typeof formSchema>

function apiTime(value: string) {
  return value.length === 16 ? `${value}:00Z` : value
}

const nameFields = [
  {
    name: "venue_id",
    label: "Venue",
    placeholder: "Main Hall",
    queryKey: "venues",
    search: async (query: string) => {
      const result = await EventsService.suggestVenues({
        query: { q: query, limit: 10 },
      })
      return (result.data?.data ?? []).map((row) => ({
        id: row.id,
        name: row.name,
      }))
    },
  },
  {
    name: "performer_id",
    label: "Performer",
    placeholder: "The Band",
    queryKey: "performers",
    search: async (query: string) => {
      const result = await EventsService.suggestPerformers({
        query: { q: query, limit: 10 },
      })
      return (result.data?.data ?? []).map((row) => ({
        id: row.id,
        name: row.name,
        hint: row.genre,
      }))
    },
  },
] as const

const AddEvent = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      description: "",
      venue_id: "",
      performer_id: "",
      time: "",
      price: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: EventCreate) =>
      EventsService.createEvent({ body: data }),
    onSuccess: () => {
      showSuccessToast("Event created successfully")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({
      name: data.name,
      description: data.description || null,
      venue_id: data.venue_id,
      performer_id: data.performer_id,
      time: apiTime(data.time),
      price: Number(data.price),
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          Add Event
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Event</DialogTitle>
          <DialogDescription>
            Fill in the details to add a new event.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Name"
                        type="text"
                        {...field}
                        required
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Input placeholder="Description" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {nameFields.map((picker) => (
                <FormField
                  key={picker.name}
                  control={form.control}
                  name={picker.name}
                  render={({ field, fieldState }) => (
                    <FormItem>
                      <NamePicker
                        label={picker.label}
                        placeholder={picker.placeholder}
                        queryKey={picker.queryKey}
                        id={field.value}
                        error={fieldState.error?.message}
                        onPick={field.onChange}
                        search={picker.search}
                      />
                    </FormItem>
                  )}
                />
              ))}
              <FormField
                control={form.control}
                name="time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Time <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} required />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Price <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        step="0.01"
                        {...field}
                        required
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddEvent
