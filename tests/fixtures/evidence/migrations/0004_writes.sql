create policy "session_set insert" on session_set for INSERT POLICY with check (owner = auth.uid());
