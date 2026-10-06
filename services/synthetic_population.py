from __future__ import annotations
import csv, random, re, statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from services.source_catalog import load_exam_modules, load_module_year_map, load_programme_map

FIRST=['Thabo','Lerato','Kabelo','Naledi','Karabo','Tshegofatso','Refilwe','Bokang','Neo','Kagiso','Palesa','Oratile','Amogelang','Lesego','Tebogo','Mpho','Lethabo','Keitumetse','Siyabonga','Noluthando','Lwazi','Ayanda','Zanele','Siphesihle','Amahle','Nkosinathi','Buhle','Anele','Onke','Khanyisa']
LAST=['Mokoena','Ndlovu','Molefe','Khumalo','Dlamini','Mthembu','Mahlangu','Mabaso','Maseko','Mokoena','Moagi','Modise','Motsamai','Mogale','Masilo','Mofokeng','Mokoatsi','Mabena','Molepo','Makhubela','Mthembu','Nkomo','Zulu','Ngwenya','Sithole','Mthembu','Radebe','Baloyi','Mahlangu','Mokoena']
@dataclass(frozen=True)
class GeneratedStudent:
    student_number:str; first_name:str; last_name:str; email:str; password:str; programme_code:str; year_level:int; section_code:str
@dataclass(frozen=True)
class GeneratedLecturer:
    staff_number:str; first_name:str; last_name:str; email:str; password:str; faculty_code:str; department_code:str
@dataclass(frozen=True)
class GeneratedRegistration:
    student_number:str; module_code:str
@dataclass
class PopulationBundle:
    students:list[GeneratedStudent]; lecturers:list[GeneratedLecturer]; registrations:list[GeneratedRegistration]; report_rows:list[dict]; module_lecturer:dict[str,str]

def generate_population(data_dir:Path, seed=20260922, min_students=3000, max_students=5000):
    data_dir=Path(data_dir); rnd=random.Random(seed); exam=load_exam_modules(data_dir/'source_exam_modules.csv'); pmap=load_programme_map(data_dir/'programme_faculty_map.csv'); my=load_module_year_map(data_dir/'module_year_map.csv')
    year_map={(r['programme_code'],r['module_code']):int(r['year_level']) for r in my}
    source_groups=defaultdict(list)
    for r in exam: source_groups[r.source_group_id].append(r)
    estimates=defaultdict(list)
    for grp in source_groups.values():
        progs=sorted({r.programme_code for r in grp}); cnt=max(r.source_students for r in grp); share=max(12, round(cnt/max(1,len(progs))))
        for p in progs: estimates[p].append(share)
    cohort={p:max(35,int(round(statistics.median(v)))) for p,v in estimates.items()}
    total=sum(cohort.values()); target=min(max(4000,min_students),max_students); factor=target/total if total else 1
    cohort={p:max(35,int(round(n*factor))) for p,n in cohort.items()}
    # adjust into range
    total=sum(cohort.values())
    if total<min_students:
        keys=sorted(cohort); i=0
        while total<min_students: cohort[keys[i%len(keys)]]+=1; total+=1; i+=1
    if total>max_students:
        keys=sorted(cohort,key=cohort.get,reverse=True); i=0
        while total>max_students:
            k=keys[i%len(keys)]
            if cohort[k]>35: cohort[k]-=1; total-=1
            i+=1
    # dominant year for each programme from its module relations; students spread across observed years
    years=defaultdict(list)
    for r in exam: years[r.programme_code].append(year_map.get((r.programme_code,r.module_code),1))
    students=[]; by_prog_year=defaultdict(list); serial=10001
    used_names=defaultdict(int)
    for p in sorted(cohort):
        yset=sorted(set(years[p])) or [1]
        n=cohort[p]
        for idx in range(n):
            y=yset[idx%len(yset)]
            section=chr(65+((idx//80)%26))
            fn=rnd.choice(FIRST); ln=rnd.choice(LAST); used_names[(fn,ln)]+=1
            sn=f'2026{serial:05d}'; serial+=1
            s=GeneratedStudent(sn,fn,ln,f'{sn}@tnu.ac.za','Tnu@'+sn[-4:],p,y,section)
            students.append(s); by_prog_year[(p,y)].append(s)
    # module registrations based on source groups and target counts; each module de-duped
    regset=set(); module_targets=defaultdict(int); module_progs=defaultdict(set)
    for gid,grp in source_groups.items():
        module=grp[0].module_code; target=max(r.source_students for r in grp); progs=sorted({r.programme_code for r in grp}); module_targets[module]+=target; module_progs[module].update(progs)
        eligible=[]
        for p in progs:
            y=year_map.get((p,module),1); eligible += by_prog_year.get((p,y),[])
        rnd.shuffle(eligible)
        for s in eligible[:min(target,len(eligible))]: regset.add((s.student_number,module))
    # ensure every synthetic student has at least two modules from their programme/year
    available=defaultdict(list)
    for r in exam:
        y=year_map.get((r.programme_code,r.module_code),1)
        if r.module_code not in available[(r.programme_code,y)]: available[(r.programme_code,y)].append(r.module_code)
    current=defaultdict(set)
    for sn,m in regset: current[sn].add(m)
    for st in students:
        choices=list(available.get((st.programme_code,st.year_level),[]))
        rnd.shuffle(choices)
        for m in choices:
            if len(current[st.student_number])>=2: break
            regset.add((st.student_number,m)); current[st.student_number].add(m)
    regs=[GeneratedRegistration(a,b) for a,b in sorted(regset)]
    # faculty-specific synthetic lecturers and assignments, approx 2-4 modules each
    modules=sorted({r.module_code for r in exam}); module_fac={m:next(r.faculty_code for r in exam if r.module_code==m) for m in modules}
    lecturers=[]; fac_lecturers=defaultdict(list); lserial=1; used_emails=set()
    for fac in ['EDU','EMS','HUM','NAS']:
        facmods=[m for m in modules if module_fac[m]==fac]; need=max(4,(len(facmods)+2)//3)
        dept={'EDU':'EDU','EMS':'BUS','HUM':'HUM','NAS':'SCI'}[fac]
        for _ in range(need):
            fn=rnd.choice(FIRST); ln=rnd.choice(LAST); staff=f'TNU{lserial:05d}'; lserial+=1
            base=f'{fn}.{ln}'.lower(); email=f'{base}@tnu.ac.za'; k=2
            while email in used_emails: email=f'{base}{k}@tnu.ac.za'; k+=1
            used_emails.add(email)
            l=GeneratedLecturer(staff,fn,ln,email,'Tnu@'+staff[-4:],fac,dept); lecturers.append(l); fac_lecturers[fac].append(l)
    module_lecturer={}
    fac_index=defaultdict(int)
    for m in modules:
        fac=module_fac[m]; ls=fac_lecturers[fac]; l=ls[fac_index[fac]%len(ls)]; fac_index[fac]+=1; module_lecturer[m]=l.staff_number
    # report
    actual=defaultdict(int)
    for r in regs: actual[r.module_code]+=1
    report=[]
    for m in modules:
        src=module_targets[m]; gen=actual[m]; report.append({'module_code':m,'source_students':src,'generated_students':gen,'absolute_difference':abs(src-gen),'percentage_difference':round(abs(src-gen)/src*100,1) if src else 0,'programmes':'|'.join(sorted(module_progs[m]))})
    return PopulationBundle(students,lecturers,regs,report,module_lecturer)
