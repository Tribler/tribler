'use client';
import { triblerService } from '@/services/tribler.service';
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
                return await triblerService.getCompletions(value);
            }}
            onChange={(query) => navigate('/search?query=' + query)}
        />
    );
};
