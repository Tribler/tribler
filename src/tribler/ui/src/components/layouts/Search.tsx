'use client';
import { triblerService } from '@/services/tribler.service';
import { isErrorDict } from "@/services/reporting";
import { Autocomplete } from '../ui/autocomplete';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';


export function Search() {
    const navigate = useNavigate();
    const { t } = useTranslation();
    return (
        <Autocomplete
            placeholder={t('SearchPlaceholder')}
            completions={async (value) => {
                const response = await triblerService.getCompletions(value);
                if (response === undefined || isErrorDict(response)) {
                    return [];
                } else {
                    return response;
                }
            }}
            onChange={(query) => navigate('/search?query=' + query)}
        />
    );
};
