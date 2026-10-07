create policy "session_set read" on session_set for select using (owner = auth.uid());
